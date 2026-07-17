import hashlib
from pathlib import Path

import pytest

from brp.artifacts import ArtifactStorageError, LocalArtifactStore, safe_storage_key


def test_local_artifacts_are_content_addressed_and_confined(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    content = b"governed release"
    stored = store.put("releases/example.bin", content)
    assert stored.content_hash == hashlib.sha256(content).hexdigest()
    assert stored.size_bytes == len(content)
    assert store.get(stored.storage_key) == content


@pytest.mark.parametrize("key", ["../secret", "/", "bad key", "a/../../b"])
def test_unsafe_artifact_keys_are_rejected(key: str) -> None:
    with pytest.raises(ArtifactStorageError):
        safe_storage_key(key)
