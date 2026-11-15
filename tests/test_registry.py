import pytest
from pydantic import ValidationError

from japanese_ai.model_registry.registry import ModelRegistry, RegistryFile

BASE = {
    "id": "a",
    "capability": "asr",
    "provider": "sherpa_onnx",
    "deployment": "local",
    "languages": ["ja"],
    "license": "MIT",
    "source": "x",
}


def test_packaged_registry_is_valid():
    registry = ModelRegistry.load()
    chain = registry.chain("asr")
    assert chain and chain[0].id == registry.routing("asr").primary
    assert all(spec.enabled for spec in chain)


def test_unknown_routing_reference_is_rejected():
    with pytest.raises(ValidationError, match="unknown model"):
        RegistryFile.model_validate({"models": [BASE], "routing": {"asr": {"primary": "missing"}}})


def test_duplicate_ids_are_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        RegistryFile.model_validate({"models": [BASE, BASE], "routing": {"asr": {"primary": "a"}}})


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        RegistryFile.model_validate({"models": [{**BASE, "typo": 1}], "routing": {"asr": {"primary": "a"}}})


def test_chain_skips_disabled_and_respects_override():
    data = RegistryFile.model_validate(
        {
            "models": [BASE, {**BASE, "id": "b"}, {**BASE, "id": "c", "enabled": False}],
            "routing": {"asr": {"primary": "a", "fallbacks": ["c", "b"]}},
        }
    )
    registry = ModelRegistry(data)
    assert [m.id for m in registry.chain("asr")] == ["a", "b"]
    assert [m.id for m in registry.chain("asr", primary_override="b")] == ["b"]
    assert [m.id for m in registry.chain("asr", preferred="b")] == ["b"]
    assert registry.chain("asr", preferred="c") == []
    assert registry.chain("asr", preferred="nope") == []
