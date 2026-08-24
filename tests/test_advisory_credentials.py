import os

import pytest

from arx.advisory.credentials import (
    CredentialSource,
    CredentialState,
    CredentialUnreadable,
    ProviderCredentialResolver,
    WindowsDPAPICredentialStore,
    import_openai_credential_file,
)


FIRST = bytearray(b"sk-proj-arx4-fixture-first-credential")
SECOND = bytearray(b"sk-proj-arx4-fixture-replacement-credential")


def _mock_store(tmp_path, *, unprotector=None):
    protected = {}

    def protect(value):
        protected["plain"] = bytes(value)
        return b"mock-protected:" + bytes(reversed(value))

    def unprotect(value):
        if unprotector:
            return unprotector(value)
        assert value.startswith(b"mock-protected:")
        return bytearray(reversed(value.removeprefix(b"mock-protected:")))

    return WindowsDPAPICredentialStore(
        "openai-api",
        path=tmp_path / "openai-api.dpapi",
        protector=protect,
        unprotector=unprotect,
    ), protected


def test_missing_credential_is_not_configured(tmp_path):
    store, _ = _mock_store(tmp_path)

    status = store.status()

    assert status.state is CredentialState.NOT_CONFIGURED
    assert status.source is CredentialSource.NONE
    assert not store.exists()


def test_protected_store_round_trip_never_writes_plaintext(tmp_path):
    store, captured = _mock_store(tmp_path)

    status = store.save(FIRST)

    assert status.state is CredentialState.CONFIGURED
    assert captured["plain"] == bytes(FIRST)
    assert bytes(FIRST) not in store.path.read_bytes()
    with store.lease() as lease:
        assert lease.text() == FIRST.decode("ascii")
        assert "credential" not in repr(lease).casefold() or "redacted" in repr(lease).casefold()
    assert store.status().state is CredentialState.CONFIGURED


def test_unreadable_blob_is_distinct_from_not_configured(tmp_path):
    def fail(_value):
        raise CredentialUnreadable("mock context mismatch")

    store, _ = _mock_store(tmp_path, unprotector=fail)
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_bytes(b"ARX4-DPAPI-CREDENTIAL\x00\x01opaque")

    status = store.status()

    assert status.state is CredentialState.CREDENTIAL_UNREADABLE
    assert status.source is CredentialSource.SECURE_WINDOWS_STORE
    assert "cannot be decrypted" in status.message


def test_credential_replace_and_remove_are_explicit(tmp_path):
    store, _ = _mock_store(tmp_path)
    store.save(FIRST)
    store.save(SECOND)

    with store.lease() as lease:
        assert lease.text() == SECOND.decode("ascii")
    assert bytes(FIRST) not in store.path.read_bytes()
    assert bytes(SECOND) not in store.path.read_bytes()

    status = store.remove()
    assert status.state is CredentialState.NOT_CONFIGURED
    assert not store.path.exists()


def test_environment_source_precedes_secure_store_without_persistence(tmp_path):
    store, _ = _mock_store(tmp_path)
    resolver = ProviderCredentialResolver(
        "openai-api",
        "OPENAI_API_KEY",
        store,
        environment_getter=lambda _name: FIRST.decode("ascii"),
    )

    status = resolver.status()

    assert status.state is CredentialState.CONFIGURED
    assert status.source is CredentialSource.PROCESS_ENVIRONMENT
    assert not store.path.exists()
    with resolver.lease() as lease:
        assert lease.source is CredentialSource.PROCESS_ENVIRONMENT
        assert lease.text() == FIRST.decode("ascii")


def test_plaintext_import_is_bounded_then_only_dpapi_blob_remains_in_store(tmp_path):
    source = tmp_path / "downloaded-key.txt"
    source.write_bytes(b"OPENAI_API_KEY='" + bytes(FIRST) + b"'\r\n")
    store, _ = _mock_store(tmp_path)

    status = import_openai_credential_file(source, store)

    assert status.state is CredentialState.CONFIGURED
    assert source.exists()
    assert bytes(FIRST) not in store.path.read_bytes()


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI is Windows-only")
def test_real_windows_dpapi_round_trip_uses_current_user_context(tmp_path):
    store = WindowsDPAPICredentialStore("openai-api", path=tmp_path / "openai-api.dpapi")
    secret = bytearray(FIRST)
    try:
        store.save(secret)
        assert bytes(secret) not in store.path.read_bytes()
        with store.lease() as lease:
            assert lease.text() == FIRST.decode("ascii")
    finally:
        for index in range(len(secret)):
            secret[index] = 0
