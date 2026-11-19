"""Render the production database, Redis and Django credentials for Compose."""

import os
import sys
from pathlib import Path

MYSQL_KEYS = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD")
RUNTIME_KEYS = ("SECRET_KEY", "REDIS_URL", "DATABASE_URL", *MYSQL_KEYS)


def write_runtime_env(path: Path) -> None:
    values = {key: os.environ.get(key, "") for key in RUNTIME_KEYS}
    if not any(values.values()):
        return

    # The target resolves the effective mode (including legacy deployments)
    # and validates the broker after Compose merges the runtime environment.
    required = ("SECRET_KEY",)
    if not values["DATABASE_URL"]:
        required += tuple(key for key in MYSQL_KEYS if key != "MYSQL_PORT")
        values["MYSQL_PORT"] = values["MYSQL_PORT"] or "3306"
    missing = [key for key in required if not values[key].strip()]
    if missing:
        raise SystemExit(f"缺少生产运行配置: {', '.join(missing)}")

    for key, value in values.items():
        if any(character in value for character in ("\n", "\r", "\x00")):
            raise SystemExit(f"{key} 必须为单行值")
    # Compose reads this file in raw mode, preserving literal quotes and dollar signs.
    with open(path, "x", encoding="utf-8", opener=private_open) as stream:
        stream.writelines(f"{key}={value}\n" for key, value in values.items())


def private_open(path: str, flags: int) -> int:
    return os.open(path, flags, 0o600)


if __name__ == "__main__":
    write_runtime_env(Path(sys.argv[1]))
