"""Object storage settings helpers."""

from collections.abc import Mapping

from django.core.exceptions import ImproperlyConfigured


_TRUE_VALUES = {"1", "true", "yes", "on"}


def r2_storage_enabled(environ: Mapping[str, str]) -> bool:
    """Return whether Cloudflare R2 storage is explicitly enabled."""
    return environ.get("USE_R2_STORAGE", "false").strip().lower() in _TRUE_VALUES


def build_r2_storages(environ: Mapping[str, str]) -> dict | None:
    """Build Django 4.2 STORAGES config for a private Cloudflare R2 bucket.

    Local filesystem storage remains Django's default unless R2 is explicitly
    enabled. Enabling R2 fails fast when credentials are incomplete so uploads
    cannot silently fall back to a container's ephemeral filesystem.
    """
    if not r2_storage_enabled(environ):
        return None

    required = {
        "R2_ACCESS_KEY_ID": environ.get("R2_ACCESS_KEY_ID", "").strip(),
        "R2_SECRET_ACCESS_KEY": environ.get("R2_SECRET_ACCESS_KEY", "").strip(),
        "R2_BUCKET_NAME": environ.get("R2_BUCKET_NAME", "").strip(),
    }
    missing = [name for name, value in required.items() if not value]

    endpoint_url = environ.get("R2_ENDPOINT_URL", "").strip()
    account_id = environ.get("R2_ACCOUNT_ID", "").strip()
    if not endpoint_url and not account_id:
        missing.append("R2_ACCOUNT_ID or R2_ENDPOINT_URL")

    if missing:
        raise ImproperlyConfigured(
            "Cloudflare R2 storage is enabled but required settings are missing: "
            + ", ".join(missing)
        )

    if not endpoint_url:
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

    try:
        signed_url_expire = int(environ.get("R2_SIGNED_URL_EXPIRE_SECONDS", "900"))
    except ValueError as exc:
        raise ImproperlyConfigured(
            "R2_SIGNED_URL_EXPIRE_SECONDS must be an integer"
        ) from exc
    if signed_url_expire <= 0:
        raise ImproperlyConfigured(
            "R2_SIGNED_URL_EXPIRE_SECONDS must be greater than zero"
        )

    return {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "access_key": required["R2_ACCESS_KEY_ID"],
                "secret_key": required["R2_SECRET_ACCESS_KEY"],
                "bucket_name": required["R2_BUCKET_NAME"],
                "endpoint_url": endpoint_url.rstrip("/"),
                "region_name": environ.get("R2_REGION_NAME", "auto").strip() or "auto",
                "signature_version": "s3v4",
                "default_acl": None,
                "querystring_auth": True,
                "querystring_expire": signed_url_expire,
                "file_overwrite": False,
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
