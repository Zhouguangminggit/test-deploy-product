import json
import time
import zipfile
from base64 import urlsafe_b64encode
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.test import Client, override_settings

from apps.licensing import services
from scripts import package


def encoded(value):
    return urlsafe_b64encode(value).decode().rstrip("=")


def make_lease(key, now, **overrides):
    header = encoded(json.dumps({"alg": "EdDSA", "kid": "v1"}).encode())
    payload = {
        "version": 1,
        "product_id": "12",
        "device_digest": "device",
        "iat": int(now),
        "exp": int(now) + 604800,
        "license_id": "1",
        "binding_version": 1,
    }
    payload.update(overrides)
    body = encoded(json.dumps(payload).encode())
    signature = encoded(key.sign(f"{header}.{body}".encode()))
    return f"{header}.{body}.{signature}"


@pytest.fixture
def licensed(tmp_path):
    key = Ed25519PrivateKey.generate()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    with (
        override_settings(
            BASE_DIR=tmp_path,
            LICENSE_ENABLED=True,
            LICENSE_BYPASS=False,
            LICENSE_PRODUCT_ID="12",
            LICENSE_SERVER_URL="https://example.test/product-manage",
            LICENSE_PUBLIC_KEYS=json.dumps({"v1": public}),
        ),
        patch.object(services, "device_digest", return_value="device"),
    ):
        yield key


def test_activation_and_offline_lease(licensed):
    now = time.time()
    token = make_lease(licensed, now)
    with patch.object(services, "request_server", return_value=token):
        services.activate("secret")
    with patch.object(services, "request_server") as request:
        services.check_license()
        request.assert_not_called()
    assert (services.cache_dir() / "state.json").stat().st_mode & 0o077 == 0


def test_explicit_rejection_is_not_offline_grace(licensed):
    token = make_lease(licensed, time.time())
    with patch.object(services, "request_server", return_value=token):
        services.activate("secret")
    state = services.read_cache()
    state["last_online"] -= 86401
    services.write_cache(state)
    with (
        patch.object(services, "request_server", side_effect=services.LicenseError("DISABLED")),
        pytest.raises(services.LicenseError, match="DISABLED"),
    ):
        services.check_license()
    with (
        patch.object(
            services, "request_server", side_effect=services.LicenseError("TEMPORARY_UNAVAILABLE")
        ),
        pytest.raises(services.LicenseError, match="DISABLED"),
    ):
        services.check_license()


def test_signature_product_and_expiry(licensed):
    now = time.time()
    _, keys = services.configuration()
    for token in (
        make_lease(licensed, now, product_id="13"),
        make_lease(licensed, now, device_digest="other"),
        make_lease(Ed25519PrivateKey.generate(), now),
    ):
        with pytest.raises(services.LicenseError):
            services.verify_lease(token, "12", "device", keys, now)
    with pytest.raises(services.LicenseError, match="EXPIRED"):
        services.verify_lease(make_lease(licensed, now - 604800), "12", "device", keys, now)


def test_guard_and_csrf(client, licensed):
    response = client.get("/admin/", HTTP_ACCEPT="text/html")
    assert response.status_code == 403
    assert "产品未经授权" in response.content.decode()
    assert client.get("/static/missing.css").status_code == 403
    assert client.get("/healthz/").status_code == 200
    assert client.get("/license/activate/").status_code == 200

    assert (
        Client(enforce_csrf_checks=True).post("/license/activate/", {"code": "secret"}).status_code
        == 403
    )


def test_invalid_configuration_blocks(client):
    with override_settings(
        LICENSE_ENABLED=True,
        LICENSE_BYPASS=False,
        LICENSE_PRODUCT_ID="",
        LICENSE_SERVER_URL="",
        LICENSE_PUBLIC_KEYS="{}",
    ):
        response = client.get("/", HTTP_ACCEPT="application/json")
    assert response.status_code == 403
    assert response.json()["code"] == "CONFIG_ERROR"


def test_package_rejects_bypass_and_excludes_license_cache(tmp_path, monkeypatch):
    root = tmp_path / "product"
    root.mkdir()
    (root / ".env.local").write_text("LICENSE_ENABLED=False\nLICENSE_BYPASS=True\n")
    with pytest.raises(ValueError):
        package.validate_license_config(root / ".env.local")
    (root / ".env.local").write_text("DEBUG=False\n")
    (root / ".license").mkdir()
    (root / ".license" / "state.json").write_text("secret")
    (root / "app.py").write_text("pass")
    monkeypatch.setattr(package, "PROJECT_ROOT", root)
    monkeypatch.setattr(package, "PROJECT_NAME", "product")
    archive = package.build_package()
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert "product/.env" in names
        assert b"LICENSE_ENABLED=False" in bundle.read("product/.env")
        assert not any(".license/" in name for name in names)


def test_offline_outage_and_clock_rollback(licensed):
    now = time.time()
    token = make_lease(licensed, now)
    with patch.object(services, "request_server", return_value=token):
        services.activate("secret")
    state = services.read_cache()
    state["last_online"] -= 86401
    services.write_cache(state)
    with patch.object(
        services, "request_server", side_effect=services.LicenseError("TEMPORARY_UNAVAILABLE")
    ):
        services.check_license()
        state = services.read_cache()
        state["last_seen"] = now + 600
        services.write_cache(state)
        with pytest.raises(services.LicenseError, match="CLOCK_ERROR"):
            services.check_license()


def test_http_client_does_not_redirect_or_disable_tls(licensed):
    response = type(
        "Response",
        (),
        {"status_code": 200, "json": lambda self: {"data": {"code": "OK", "lease": "token"}}},
    )()
    with patch.object(services.requests, "post", return_value=response) as post:
        assert services.request_server("activate", "secret", "12", "device") == "token"
    assert post.call_args.kwargs["allow_redirects"] is False
    assert post.call_args.kwargs.get("verify", True) is True
