import json

import pandas as pd
import pytest

from quantrail.core import Declaration, PriceBasis, Provenance
from quantrail.datasets import export_dataset, ingest, list_versions, load_dataset, write_dataset


def codes(dataset):
    return {f.code for f in dataset.trust.flags}


def prices(**extra):
    frame = pd.DataFrame({"date": ["2024-01-03", "2024-01-02", "2024-01-04"],
                          "close": [101.0, 100.0, 102.0]})
    for key, values in extra.items():
        frame[key] = values
    return frame


def test_minimal_table_is_accepted_and_every_unknown_is_reported(tmp_path):
    ds = ingest(prices(), root=tmp_path, dataset_id="mine", version="v1")
    assert list(ds.tables["prices"]["close"]) == [100.0, 101.0, 102.0]  # sorted by date
    assert codes(ds) == {"SOURCE_UNKNOWN", "LICENCE_UNKNOWN", "PRICE_BASIS_UNKNOWN",
                         "ACCOUNTING_APPROXIMATE", "AVAILABILITY_UNVERIFIED", "NO_OPEN_PRICES"}


def test_fully_declared_raw_data_with_events_is_clean(tmp_path):
    events = pd.DataFrame({"ex_date": ["2024-01-03"], "cash": [1.0]})
    ds = ingest(prices(open=[100.5, 99.5, 101.5], high=[102.0, 101.0, 103.0], low=[100.0, 99.0, 101.0]),
                root=tmp_path, dataset_id="clean", version="v1",
                provenance=Provenance("Open data portal", "CC-BY-4.0"),
                declaration=Declaration(PriceBasis.RAW, "close"), corporate_actions=events)
    assert ds.trust.clean
    assert ds.declaration.corporate_actions is True
    assert "corporate_actions" in ds.tables


def test_inconsistent_ohlc_is_kept_and_flagged_not_repaired(tmp_path):
    ds = ingest(prices(open=[100.0, 100.0, 100.0], high=[99.0, 101.0, 103.0], low=[98.0, 99.0, 99.0]),
                root=tmp_path, dataset_id="ohlc", version="v1")
    table = ds.tables["prices"].set_index("date")
    assert not table.loc["2024-01-03", "quote_valid"]  # high 99 < open 100
    assert "INVALID_QUOTES" in codes(ds) and ds.manifest["checks"]["invalid_quotes"] == 1


@pytest.mark.parametrize("bad", [
    pd.DataFrame({"date": ["2024-01-02", "2024-01-02"], "close": [1.0, 2.0]}),
    pd.DataFrame({"date": ["2024-01-02"], "close": [0.0]}),
    pd.DataFrame({"date": ["2024-01-02"], "close": ["n/a"]}),
    pd.DataFrame({"day": ["2024-01-02"], "close": [1.0]}),
])
def test_unpriceable_rows_are_refused(tmp_path, bad):
    with pytest.raises(ValueError):
        ingest(bad, root=tmp_path, dataset_id="bad", version="v1")


def test_csv_path_and_custom_date_column(tmp_path):
    path = tmp_path / "p.csv"
    prices().rename(columns={"date": "trade_date"}).to_csv(path, index=False)
    ds = ingest(path, root=tmp_path / "store", dataset_id="csv", version="v1", date_column="trade_date",
                instrument="TWSE:0050")
    assert set(ds.tables["prices"]["instrument"]) == {"TWSE:0050"}


def test_versions_are_explicit_and_never_overwritten(tmp_path):
    ingest(prices(), root=tmp_path, dataset_id="d", version="v1")
    ingest(prices(), root=tmp_path, dataset_id="d", version="v2")
    assert list_versions(tmp_path, "d") == ["v1", "v2"]
    with pytest.raises(ValueError, match="latest"):
        load_dataset(tmp_path, "d", None)
    with pytest.raises(FileExistsError):
        ingest(prices(), root=tmp_path, dataset_id="d", version="v1")


def test_tampering_is_detected(tmp_path):
    ds = write_dataset(tmp_path, "t", {"prices": prices()}, version="v1")
    path = tmp_path / "t" / "v1" / ds.manifest["tables"]["prices"]["file"]
    pd.DataFrame({"date": ["x"], "close": [9.0]}).to_parquet(path, index=False)
    with pytest.raises(ValueError, match="Hash mismatch"):
        load_dataset(tmp_path, "t", "v1")


def test_manifest_identity_must_match(tmp_path):
    write_dataset(tmp_path, "a", {"prices": prices()}, version="v1")
    manifest = tmp_path / "a" / "v1" / "manifest.json"
    data = json.loads(manifest.read_text())
    data["dataset_id"] = "b"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="identity"):
        load_dataset(tmp_path, "a", "v1")


def test_export_requires_known_licence_or_acknowledgement(tmp_path):
    unknown = ingest(prices(), root=tmp_path / "s", dataset_id="u", version="v1")
    with pytest.raises(PermissionError):
        export_dataset(unknown, tmp_path / "s", tmp_path / "out")
    target = export_dataset(unknown, tmp_path / "s", tmp_path / "out", acknowledge_unknown_license=True)
    notice = (target / "EXPORT_NOTICE.txt").read_text()
    assert "acknowledged that the licence is unknown" in notice and "LICENCE_UNKNOWN" in notice

    known = ingest(prices(), root=tmp_path / "s", dataset_id="k", version="v1",
                   provenance=Provenance("Open data portal", "CC-BY-4.0"))
    assert (export_dataset(known, tmp_path / "s", tmp_path / "out") / "manifest.json").is_file()
