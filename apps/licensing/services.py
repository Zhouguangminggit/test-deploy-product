"""本机授权客户端；不记录授权码、设备标识或租约。"""

import base64
import hashlib
import json
import os
import platform
import re
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.conf import settings

if os.name == "nt":
    import msvcrt
    import winreg
else:
    import fcntl

_LOCK = threading.RLock()
_DENIED = {"INVALID_LICENSE", "DEVICE_LIMIT", "DISABLED", "NOT_BOUND"}


class LicenseError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def configuration():
    try:
        product = settings.LICENSE_PRODUCT_ID
        url = urlsplit(settings.LICENSE_SERVER_URL)
        keys = json.loads(settings.LICENSE_PUBLIC_KEYS)
        if not re.fullmatch(r"[0-9]+", product) or int(product) <= 0:
            raise ValueError
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError
        if not isinstance(keys, dict) or not keys:
            raise ValueError
        for kid, pem in keys.items():
            if not kid or not isinstance(
                serialization.load_pem_public_key(pem.encode()), Ed25519PublicKey
            ):
                raise ValueError
        return product, keys
    except (ValueError, TypeError, AttributeError):
        raise LicenseError("CONFIG_ERROR") from None


def device_digest(product):
    try:
        system = platform.system()
        if system == "Linux":
            raw = Path("/etc/machine-id").read_text().strip()
        elif system == "Darwin":
            result = subprocess.run(
                ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', result.stdout)
            raw = match.group(1) if match else ""
        elif system == "Windows":
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                raw = winreg.QueryValueEx(key, "MachineGuid")[0]
        else:
            raw = ""
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError
        return hashlib.sha256(f"license-v1:{product}:{raw.strip()}".encode()).hexdigest()
    except (OSError, ValueError, subprocess.SubprocessError):
        raise LicenseError("DEVICE_ERROR") from None


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_lease(token, product, device, keys, now):
    try:
        header, payload, signature = token.split(".")
        metadata = json.loads(_decode(header))
        body = json.loads(_decode(payload))
        if metadata.get("alg") != "EdDSA":
            raise ValueError
        key = serialization.load_pem_public_key(keys[metadata["kid"]].encode())
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError
        key.verify(_decode(signature), f"{header}.{payload}".encode("ascii"))
        if body["version"] != 1 or body["product_id"] != product or body["device_digest"] != device:
            raise ValueError
        issued, expiry = int(body["iat"]), int(body["exp"])
        if expiry <= issued or expiry - issued > 7 * 86400 or now >= expiry:
            raise LicenseError("EXPIRED")
        if now < issued - 300:
            raise LicenseError("CLOCK_ERROR")
        return body
    except LicenseError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, InvalidSignature, UnicodeError):
        raise LicenseError("INVALID_CACHE") from None


def cache_dir():
    return settings.BASE_DIR / ".license"


def read_cache():
    try:
        data = json.loads((cache_dir() / "state.json").read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or not isinstance(data["code"], str)
            or not isinstance(data["lease"], str)
        ):
            raise ValueError
        return data
    except (OSError, ValueError, KeyError, TypeError):
        raise LicenseError("NOT_ACTIVATED") from None


def write_cache(data):
    directory = cache_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(directory, 0o700)
    fd, name = tempfile.mkstemp(dir=directory, prefix=".state-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, directory / "state.json")
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def cache_lock():
    with _LOCK:
        directory = cache_dir()
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(directory, 0o700)
        with (directory / "lock").open("a+b") as stream:
            if os.name != "nt":
                os.chmod(directory / "lock", 0o600)
            if os.name == "nt":
                stream.seek(0)
                if not stream.read(1):
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)


def request_server(action, code, product, device):
    try:
        response = requests.post(
            settings.LICENSE_SERVER_URL.rstrip("/") + "/public/licenses/" + action,
            json={"product_id": product, "license_code": code, "device_id": device},
            timeout=(3, 5),
            allow_redirects=False,
        )
        if response.status_code == 429 or response.status_code >= 500:
            raise LicenseError("TEMPORARY_UNAVAILABLE")
        if response.status_code != 200:
            raise LicenseError("TEMPORARY_UNAVAILABLE")
        result = response.json()["data"]
        status = result["code"]
        if status in _DENIED:
            raise LicenseError(status)
        if status != "OK":
            raise LicenseError("TEMPORARY_UNAVAILABLE")
        return result["lease"]
    except LicenseError:
        raise
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise LicenseError("TEMPORARY_UNAVAILABLE") from None


def activate(code):
    product, keys = configuration()
    device = device_digest(product)
    try:
        with cache_lock():
            now = time.time()
            lease = request_server("activate", code, product, device)
            verify_lease(lease, product, device, keys, now)
            write_cache({"code": code, "lease": lease, "last_online": now, "last_seen": now})
    except OSError:
        raise LicenseError("INVALID_CACHE") from None


def check_license():
    if not settings.LICENSE_ENABLED or settings.LICENSE_BYPASS:
        return
    product, keys = configuration()
    device = device_digest(product)
    try:
        with cache_lock():
            data = read_cache()
            now = time.time()
            try:
                previous = float(data["last_seen"])
                last_online = float(data["last_online"])
            except (KeyError, ValueError, TypeError):
                raise LicenseError("INVALID_CACHE") from None
            clock_error = now < previous - 300
            try:
                verify_lease(data["lease"], product, device, keys, now)
                valid = True
            except LicenseError as exc:
                if exc.code not in ("EXPIRED", "CLOCK_ERROR"):
                    raise
                valid = False
                clock_error = clock_error or exc.code == "CLOCK_ERROR"
            if not valid or clock_error or now - last_online >= 86400:
                try:
                    lease = request_server("verify", data["code"], product, device)
                    verify_lease(lease, product, device, keys, now)
                    data.update(lease=lease, last_online=now)
                    data.pop("blocked", None)
                    previous = now
                    valid = True
                    clock_error = False
                except LicenseError as exc:
                    if exc.code in _DENIED:
                        data["blocked"] = exc.code
                        write_cache(data)
                        raise
                    if data.get("blocked") and exc.code == "TEMPORARY_UNAVAILABLE":
                        raise LicenseError(data["blocked"]) from None
                    if exc.code != "TEMPORARY_UNAVAILABLE" or not valid or clock_error:
                        raise LicenseError(
                            "CLOCK_ERROR" if clock_error else ("EXPIRED" if not valid else exc.code)
                        ) from None
            if data.get("blocked"):
                raise LicenseError(data["blocked"])
            data["last_seen"] = max(now, previous)
            write_cache(data)
    except OSError:
        raise LicenseError("INVALID_CACHE") from None
