from brp.adapters.db_stored_object import PostgresStoredObjectAdapter
from brp.ir.canonical import canonical_bytes

SOURCE = """CREATE OR REPLACE FUNCTION eligibility(age integer, product_code text)
RETURNS text AS $$
BEGIN
  IF age < 18 THEN RETURN '미성년';
  ELSIF age > 65 THEN RETURN '연령 초과';
  ELSE RETURN '가입 가능';
  END IF;
END;
$$ LANGUAGE plpgsql;
"""


class Reader:
    def __init__(self, source: str) -> None:
        self.source = source
        self.calls: list[tuple[str, str]] = []

    def stored_procedure_source(self, schema: str, procedure: str) -> str:
        self.calls.append((schema, procedure))
        return self.source


def adapter(reader: Reader) -> PostgresStoredObjectAdapter:
    return PostgresStoredObjectAdapter(
        reader,
        connection_alias="BRP_PSQL_URL",
        objects=[("rules", "eligibility")],
    )


def test_maps_restricted_function_with_korean_and_exact_provenance() -> None:
    reader = Reader(SOURCE)
    source_adapter = adapter(reader)
    source = source_adapter.discover(None)[0]
    first = source_adapter.extract(source)
    second = source_adapter.extract(source)

    assert reader.calls == [("rules", "eligibility"), ("rules", "eligibility")]
    assert not first.unmappable
    assert first.source_snapshot.content_hash == second.source_snapshot.content_hash
    content = first.decisions[0].content
    assert canonical_bytes(content) == canonical_bytes(second.decisions[0].content)
    assert content.default_output == {"result": "가입 가능"}
    assert [rule.then[0].value for rule in content.rules] == ["미성년", "연령 초과"]
    reference = content.rules[0].source_references[0]
    assert reference.type == "DB_STORED_OBJECT"
    assert reference.schema_name == "rules"
    assert reference.object_name == "eligibility"
    assert reference.line_start == 4
    assert reference.line_end == 4
    assert reference.revision == first.source_snapshot.content_hash


def test_unsupported_statement_routes_whole_object_to_review_without_partial_candidate() -> None:
    unsafe = SOURCE.replace("BEGIN", "BEGIN\n  PERFORM notify_external();")
    batch = adapter(Reader(unsafe)).extract(adapter(Reader(unsafe)).discover(None)[0])
    assert not batch.decisions
    assert batch.unmappable[0].reason_code == "UNSUPPORTED_PROCEDURE_STATEMENT"
    assert "PERFORM notify_external" in batch.unmappable[0].raw_fragment
    assert batch.unmappable[0].provenance["objectName"] == "eligibility"


def test_complex_condition_and_sql_are_not_executed_or_guessed() -> None:
    complex_source = SOURCE.replace("age < 18", "age < 18 AND product_code = 'X'")
    batch = adapter(Reader(complex_source)).extract(
        adapter(Reader(complex_source)).discover(None)[0]
    )
    assert not batch.decisions
    assert batch.unmappable[0].reason_code == "UNSUPPORTED_PROCEDURE_CONDITION"


def test_discovery_is_sorted_deduplicated_and_secret_free() -> None:
    reader = Reader(SOURCE)
    source_adapter = PostgresStoredObjectAdapter(
        reader,
        connection_alias="BRP_PSQL_URL",
        objects=[("z", "b"), ("a", "x"), ("a", "x")],
    )
    discovered = source_adapter.discover(None)
    assert [item.source_id for item in discovered] == ["db-object:a.x", "db-object:z.b"]
    assert "BRP_PSQL_URL" not in str([item.locator for item in discovered])
