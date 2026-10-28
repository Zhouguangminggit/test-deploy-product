"""种子数据填充主入口。

用法（项目根目录）：
    uv run python scripts/seed_data.py                       # 填充所有模块（含图片）
    uv run python scripts/seed_data.py --no-images           # 填充所有模块（跳过图片）
    uv run python scripts/seed_data.py --module my_module    # 只填充指定模块
    uv run python scripts/seed_data.py --list                # 列出可用模块
    uv run python scripts/seed_data.py --dry-run             # 预览模式（不实际写入）

说明：
- 自动扫描 seeds/ 目录下所有模块配置（.py 文件，排除 _ 前缀）
- 按依赖关系拓扑排序后逐个执行
- 每个模块在独立事务中运行，失败自动回滚不影响其他模块
- 图片资源从 Pixabay API 实时下载并缓存到本地
"""

import argparse
import os
import sys
from pathlib import Path

# 保证直接执行脚本时项目根可导入（config / utils / seeds）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from loguru import logger  # noqa: E402

from scripts._seed_lib.engine import run_seed  # noqa: E402
from seeds import discover_modules  # noqa: E402


def print_module_list() -> None:
    """打印所有已发现的种子模块。"""
    modules = discover_modules()
    if not modules:
        print("未发现任何种子模块配置。请在 seeds/ 目录下创建配置文件。")
        return

    print(f"\n已发现 {len(modules)} 个种子模块：\n")
    for m in modules:
        deps = ", ".join(m.get("dependencies", [])) or "无"
        model_count = len(m.get("models", []))
        print(f"  {m['name']}")
        print(f"    描述: {m.get('description', '-')}")
        print(f"    模型数: {model_count}  依赖: {deps}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="种子数据填充工具")
    parser.add_argument(
        "--module",
        default=None,
        help="只填充指定模块（按 name 匹配）",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="跳过图片下载（加速开发调试）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际写入数据库",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用的种子模块",
    )
    args = parser.parse_args()

    # --list: 仅展示模块列表
    if args.list:
        print_module_list()
        return

    # 发现并加载模块配置
    modules = discover_modules()
    if not modules:
        logger.error("未发现任何种子模块，请先在 seeds/ 目录下创建配置")
        sys.exit(1)

    # 如果指定了 --module 但没有匹配到
    if args.module and args.module not in [m["name"] for m in modules]:
        logger.error("未找到模块 '{}'", args.module)
        logger.info("可用模块: {}", ", ".join(m["name"] for m in modules))
        sys.exit(1)

    # 打印执行摘要
    target = args.module or "全部"
    logger.info("种子数据填充启动")
    logger.info("  目标模块: {}", target)
    logger.info("  图片下载: {}", "跳过" if args.no_images else "启用")
    logger.info("  预览模式: {}", "是" if args.dry_run else "否")
    logger.info("")

    # 执行填充
    stats = run_seed(
        modules,
        skip_images=args.no_images,
        dry_run=args.dry_run,
        module_filter=args.module,
    )

    # 返回码：有失败项返回 1
    has_failure = any(
        isinstance(v, str) and v.startswith("FAILED")
        for mod_stats in stats.values()
        for v in mod_stats.values()
    )
    sys.exit(1 if has_failure else 0)


if __name__ == "__main__":
    main()
