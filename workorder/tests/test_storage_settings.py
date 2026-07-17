import pytest
from django.core.exceptions import ImproperlyConfigured

from config.storage import build_r2_storages, r2_storage_enabled


def _r2_environ(**overrides):
    environ = {
        "USE_R2_STORAGE": "true",
        "R2_ACCOUNT_ID": "account-id",
        "R2_ACCESS_KEY_ID": "access-key",
        "R2_SECRET_ACCESS_KEY": "secret-key",
        "R2_BUCKET_NAME": "work-order-media",
    }
    environ.update(overrides)
    return environ


def test_r2_storage_is_opt_in():
    assert r2_storage_enabled({}) is False
    assert build_r2_storages({}) is None
    assert r2_storage_enabled({"USE_R2_STORAGE": "YES"}) is True


def test_build_r2_storages_uses_private_signed_urls():
    storages = build_r2_storages(_r2_environ())

    options = storages["default"]["OPTIONS"]
    assert storages["default"]["BACKEND"] == "storages.backends.s3.S3Storage"
    assert options["endpoint_url"] == ("https://account-id.r2.cloudflarestorage.com")
    assert options["region_name"] == "auto"
    assert options["default_acl"] is None
    assert options["querystring_auth"] is True
    assert options["querystring_expire"] == 900
    assert options["file_overwrite"] is False


def test_build_r2_storages_accepts_jurisdiction_endpoint():
    storages = build_r2_storages(
        _r2_environ(
            R2_ACCOUNT_ID="",
            R2_ENDPOINT_URL=("https://account-id.eu.r2.cloudflarestorage.com/"),
            R2_SIGNED_URL_EXPIRE_SECONDS="300",
        )
    )

    options = storages["default"]["OPTIONS"]
    assert options["endpoint_url"] == ("https://account-id.eu.r2.cloudflarestorage.com")
    assert options["querystring_expire"] == 300


@pytest.mark.parametrize(
    "overrides",
    [
        {"R2_ACCESS_KEY_ID": ""},
        {"R2_SECRET_ACCESS_KEY": ""},
        {"R2_BUCKET_NAME": ""},
        {"R2_ACCOUNT_ID": "", "R2_ENDPOINT_URL": ""},
    ],
)
def test_build_r2_storages_rejects_incomplete_config(overrides):
    with pytest.raises(ImproperlyConfigured):
        build_r2_storages(_r2_environ(**overrides))


@pytest.mark.parametrize("value", ["invalid", "0", "-1"])
def test_build_r2_storages_rejects_invalid_expiry(value):
    with pytest.raises(ImproperlyConfigured):
        build_r2_storages(_r2_environ(R2_SIGNED_URL_EXPIRE_SECONDS=value))
