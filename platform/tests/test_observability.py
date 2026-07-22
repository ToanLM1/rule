from brp.observability import redact


def test_secret_redaction_covers_urls_and_named_values() -> None:
    value = "postgresql+psycopg://user:super-secret@db/brp token=abc password: hunter2"
    rendered = redact(value)
    assert "super-secret" not in rendered
    assert "abc" not in rendered
    assert "hunter2" not in rendered
    assert rendered.count("[REDACTED]") == 3
