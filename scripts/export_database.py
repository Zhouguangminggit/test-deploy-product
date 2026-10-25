"""导出数据库数据为 JSON fixture。

用法（项目根目录）：
    uv run python scripts/export_database.py [--output database/data/export_xxx.json]

说明：
- 默认导出到 database/data/export_<时间戳>.json；
- 排除 contenttypes / auth.Permission / sessions / admin 等不适合随项目迁移的内置模型；
- 产物可用于演示数据分发或环境间数据迁移（配合 scripts/import_database.py）。
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402

DEFAULT_DIR = PROJECT_ROOT / "database" / "data"
EXCLUDE = ["contenttypes", "auth.Permission", "sessions", "admin"]


def main() -> None:
    parser = argparse.ArgumentParser(description="导出数据库数据为 JSON fixture")
    parser.add_argument(
        "--output",
        default=None,
        help="输出文件路径（默认 database/data/export_<时间戳>.json）",
    )
    args = parser.parse_args()

    if args.output:
        output = Path(args.output)
    else:
        output = DEFAULT_DIR / f"export_{datetime.now():%Y%m%d_%H%M%S}.json"
    output.parent.mkdir(parents=True, exist_ok=True)

    call_command("dumpdata", exclude=EXCLUDE, output=str(output), indent=2)
    print(f"数据已导出到：{output}")


if __name__ == "__main__":
    main()
