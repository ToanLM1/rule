import json
from pathlib import Path

from brp.adapters.db_postgres import PostgresTableAdapter
from brp.config.models import load_site_profile
from brp.ir.canonical import canonical_bytes

ROOT = Path(__file__).resolve().parents[3]


class Reader:
    def sample_rows(self, schema: str, table: str, *, limit: int = 20) -> list[dict[str, object]]:
        assert schema == "public"
        assert limit == 50
        if table == "region_eligibility":
            return [
                {"region_code": "JEJU", "region_name_kr": "제주", "eligible": False},
                {"region_code": "SEOUL", "region_name_kr": "서울", "eligible": True},
            ]
        return [
            {
                "product_code": "암보험",
                "age_band": "18-39",
                "smoker": True,
                "base_rate": 100.5,
                "loading_pct": 20,
            },
            {
                "product_code": "암보험",
                "age_band": "18-39",
                "smoker": False,
                "base_rate": 100.5,
                "loading_pct": 0,
            },
        ]


def adapter() -> PostgresTableAdapter:
    return PostgresTableAdapter(
        Reader(),
        load_site_profile(ROOT / "config/sites/fixture.yaml"),
        ROOT / "config/mappings/fixture-tables.yaml",
    )


def test_mapping_is_deterministic_and_preserves_korean() -> None:
    source = next(
        item for item in adapter().discover(None) if item.source_id.endswith("rate_table")
    )
    first = adapter().extract(source)
    second = adapter().extract(source)
    assert first.source_snapshot.content_hash == second.source_snapshot.content_hash
    assert canonical_bytes(first.decisions[0].content) == canonical_bytes(
        second.decisions[0].content
    )
    rendered = canonical_bytes(first.decisions[0].content).decode("utf-8")
    assert "암보험" in rendered


def test_composite_primary_key_and_snapshot_hash_round_trip() -> None:
    source = next(
        item for item in adapter().discover(None) if item.source_id.endswith("rate_table")
    )
    batch = adapter().extract(source)
    references = [rule.source_references[0] for rule in batch.decisions[0].content.rules]
    assert list(references[0].primary_key) == ["product_code", "age_band", "smoker"]
    assert json.dumps(
        references[0].primary_key, ensure_ascii=False
    ).encode().decode() == json.dumps(references[0].primary_key, ensure_ascii=False)
    assert all(
        reference.snapshot_hash == batch.source_snapshot.content_hash for reference in references
    )
    assert all(rule.confidence == 1.0 for rule in batch.decisions[0].content.rules)
