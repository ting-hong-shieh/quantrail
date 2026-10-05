"""Versioned, hash-verified datasets and ingest() for data users bring themselves.

Layout: <root>/<dataset_id>/<version>/{<table>.parquet, manifest.json}.
Datasets are loaded by explicit version only (ADR 0005). Unknown provenance is
allowed and reported (ADR 0002); exporting requires a known licence or an explicit
acknowledgement.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

from .core import Declaration, Provenance, Severity, TrustFlag, TrustReport

SCHEMA = "quantrail.dataset/v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    version: str
    tables: dict
    manifest: dict
    manifest_sha256: str

    @property
    def provenance(self) -> Provenance:
        return Provenance.from_dict(self.manifest["provenance"])

    @property
    def declaration(self) -> Declaration:
        return Declaration.from_dict(self.manifest["declaration"])

    @property
    def trust(self) -> TrustReport:
        return TrustReport(tuple(TrustFlag(f["code"], Severity(f["severity"]), f["message"])
                                 for f in self.manifest["trust_flags"]))


def _check_id(value: str, name: str) -> str:
    if not _ID.match(value or ""):
        raise ValueError(f"{name} must match {_ID.pattern}: {value!r}")
    return value


def write_dataset(root, dataset_id, tables, *, provenance=None, declaration=None,
                  checks=None, extra_flags=(), sources=(), version=None) -> Dataset:
    """Write a new dataset version. Never overwrites an existing version."""
    provenance = provenance or Provenance()
    declaration = declaration or Declaration()
    _check_id(dataset_id, "dataset_id")
    version = _check_id(version or datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"), "version")
    folder = Path(root) / dataset_id / version
    folder.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, frame in tables.items():
        _check_id(name, "table name")
        path = folder / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        files[name] = {"file": path.name, "rows": len(frame), "columns": list(frame.columns),
                       "sha256": sha256(path.read_bytes()).hexdigest()}
    trust = provenance.trust().merge(declaration.trust(), TrustReport(tuple(extra_flags)))
    manifest = {
        "schema": SCHEMA, "dataset_id": dataset_id, "version": version,
        "created_at": datetime.now(UTC).isoformat(),
        "provenance": provenance.to_dict(), "declaration": declaration.to_dict(),
        "sources": list(sources), "tables": files, "checks": checks or {},
        "trust_flags": [{"code": f.code, "severity": f.severity.value, "message": f.message}
                        for f in trust.flags],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
                                          encoding="utf-8")
    return load_dataset(root, dataset_id, version)


def list_versions(root, dataset_id) -> list[str]:
    """Available versions, sorted. Listing never picks one for you (ADR 0005)."""
    folder = Path(root) / _check_id(dataset_id, "dataset_id")
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.iterdir() if (p / "manifest.json").is_file())


def load_dataset(root, dataset_id, version) -> Dataset:
    if not version:
        raise ValueError("A dataset version is required; there is no 'latest' (ADR 0005).")
    folder = Path(root) / _check_id(dataset_id, "dataset_id") / _check_id(version, "version")
    manifest_bytes = (folder / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    identity = (manifest.get("dataset_id"), manifest.get("version"))
    if manifest.get("schema") != SCHEMA or identity != (dataset_id, version):
        raise ValueError("Manifest identity or schema does not match the requested dataset.")
    tables = {}
    for name, item in manifest["tables"].items():
        path = folder / item["file"]
        if not path.resolve().is_relative_to(folder.resolve()):
            raise ValueError(f"Table path escapes the dataset folder: {item['file']}")
        if sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Hash mismatch: {dataset_id}/{version}/{item['file']}")
        tables[name] = pd.read_parquet(path)
    return Dataset(dataset_id, version, tables, manifest, sha256(manifest_bytes).hexdigest())


def _read(data) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    path = Path(data)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {path.suffix} (use CSV, Parquet or a DataFrame)")


def ingest(data, *, root, dataset_id, provenance=None, declaration=None,
           date_column="date", instrument=None, corporate_actions=None, version=None) -> Dataset:
    """Turn a user's price table into a versioned dataset with an honest trust report.

    Only `date_column` and `close` are required. Rows that cannot be priced at all
    (duplicate keys, non-positive or non-finite close) are refused, never repaired.
    Inconsistent OHLC rows are kept, marked `quote_valid = False` and flagged.
    """
    provenance = provenance or Provenance()
    declaration = declaration or Declaration()
    prices = _read(data)
    if date_column not in prices or "close" not in prices:
        raise ValueError(f"A price table needs at least '{date_column}' and 'close' columns.")
    prices = prices.rename(columns={date_column: "date"})
    prices["date"] = pd.to_datetime(prices["date"])
    if "instrument" not in prices:
        prices["instrument"] = instrument or "unknown"
    elif instrument is not None:
        raise ValueError("Pass `instrument` only when the table has no instrument column.")
    numeric = [c for c in ("open", "high", "low", "close", "volume") if c in prices]
    prices[numeric] = prices[numeric].apply(pd.to_numeric, errors="coerce")
    if prices.duplicated(["instrument", "date"]).any():
        raise ValueError("Duplicate (instrument, date) rows; resolve them before ingesting.")
    close = prices["close"].to_numpy(dtype=float)
    if not np.isfinite(close).all() or (close <= 0).any():
        raise ValueError("'close' must be finite and positive on every row.")
    prices = prices.sort_values(["instrument", "date"], ignore_index=True)

    valid = pd.Series(True, index=prices.index)
    ohlc = [c for c in ("open", "high", "low") if c in prices]
    if ohlc:
        cols = prices[ohlc + ["close"]]
        valid &= np.isfinite(cols.to_numpy(dtype=float)).all(axis=1) & (cols > 0).all(axis=1)
        if {"high", "low"} <= set(ohlc):
            body = prices[[c for c in ("open", "close") if c in prices]]
            valid &= (prices["low"] <= body.min(axis=1)) & (prices["high"] >= body.max(axis=1))
    prices["quote_valid"] = valid.to_numpy()

    flags, tables = [], {"prices": prices}
    invalid = int((~prices["quote_valid"]).sum())
    if invalid:
        flags.append(TrustFlag("INVALID_QUOTES", Severity.WARNING,
                               f"{invalid} rows have inconsistent OHLC and are marked quote_valid=False."))
    if "open" not in prices:
        flags.append(TrustFlag("NO_OPEN_PRICES", Severity.WARNING,
                               "No open prices: next-open execution cannot be modelled."))
    if corporate_actions is not None:
        tables["corporate_actions"] = _read(corporate_actions)
        if declaration.corporate_actions is None:
            declaration = Declaration(declaration.price_basis, declaration.availability, True)
    checks = {"rows": len(prices), "instruments": int(prices["instrument"].nunique()),
              "first_date": str(prices["date"].min().date()), "last_date": str(prices["date"].max().date()),
              "invalid_quotes": invalid}
    return write_dataset(root, dataset_id, tables, provenance=provenance, declaration=declaration,
                         checks=checks, extra_flags=flags, version=version)


def export_dataset(dataset: Dataset, root, destination, *, acknowledge_unknown_license=False) -> Path:
    """Copy a dataset for sharing, with its provenance stated next to the data.

    Refused when the licence is unknown unless the caller explicitly acknowledges it.
    """
    if not dataset.provenance.license_known and not acknowledge_unknown_license:
        raise PermissionError("Licence is unknown. Record it, or pass acknowledge_unknown_license=True "
                              "to confirm you are allowed to share this data.")
    source = Path(root) / dataset.dataset_id / dataset.version
    target = Path(destination) / dataset.dataset_id / dataset.version
    shutil.copytree(source, target)
    lines = [f"Dataset {dataset.dataset_id} version {dataset.version}",
             f"Source: {dataset.provenance.source}", f"Licence: {dataset.provenance.license}",
             f"Terms: {dataset.provenance.terms_url or 'not recorded'}", "", dataset.trust.render()]
    if acknowledge_unknown_license and not dataset.provenance.license_known:
        lines.insert(3, "The exporter acknowledged that the licence is unknown.")
    (target / "EXPORT_NOTICE.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
