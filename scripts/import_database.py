"""导入 JSON fixture 到数据库。

用法（项目根目录）：
    uv run python scripts/import_database.py [--file database/data/xxx.json] [--yes]

说明：
- 不指定 --file 时，自动选取 database/data/ 下最近更新的 .json；
- loaddata 会按主键覆盖已有数据，执行前需确认（--yes 跳过确认，供 make 一键调用）。
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402

DEFAULT_DIR = PROJECT_ROOT / "database" / "data"


def latest_fixture() -> Path | None:
    """返回 database/data/ 下最近更新的 .json 文件，不存在时返回 None。"""
    fixtures = sorted(DEFAULT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return fixtures[-1] if fixtures else None


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 JSON fixture 到数据库")
    parser.add_argument(
        "--file",
        default=None,
        help="fixture 文件路径（默认取 database/data/ 下最近的 .json）",
    )
    parser.add_argument("--yes", action="store_true", help="跳过确认直接导入")
    args = parser.parse_args()

    fixture = Path(args.file) if args.file else latest_fixture()
    if fixture is None or not fixture.exists():
        print("未找到可导入的 fixture 文件，请先执行 scripts/export_database.py 或用 --file 指定。")
        sys.exit(1)

    if not args.yes:
        answer = input(f"即将导入 {fixture}，同主键数据将被覆盖，是否继续？[y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("已取消导入。")
            return

    call_command("loaddata", str(fixture))
    print(f"导入完成：{fixture}")


if __name__ == "__main__":
    main()
