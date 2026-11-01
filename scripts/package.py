#!/usr/bin/env python3
"""
项目打包脚本

功能：
  1. 排除 .gitignore 中的文件、文档、部署、IDE、数据库、媒体资源、缓存等
  2. 自动将 .env.local 复制为 .env，供客户本地快速启动
  3. 打包脚本自身不包含在产物中
  4. 纯 Python 标准库实现，跨平台兼容 macOS / Linux / Windows

用法：
  python scripts/package.py       # 直接执行
  make package                    # 通过 Makefile 调用
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

# ── 项目根目录 ────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_NAME = PROJECT_ROOT.name

# ── 排除规则 ──────────────────────────────────────────────────────────────────

# 排除的目录名（匹配任意层级的同名目录）
EXCLUDE_DIRS: set[str] = {
    # 版本控制 / IDE / 编辑器
    ".git",
    ".idea",
    ".vscode",
    ".qoder",
    ".trae",
    ".screenshots",
    # Python 缓存与虚拟环境
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".eggs",
    # 前端依赖与构建产物
    "node_modules",
    "staticfiles",
    # 测试与工具缓存
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
    # 部署相关文件
    "deploy",
    ".github",
    # 文档与素材
    "docs",
    # 数据库与媒体
    "database",
    "media",
    "logs",
    # 临时文件与打包产物
    "temp",
    "dist",
}

# 排除的文件名（精确匹配）
EXCLUDE_FILES: set[str] = {
    ".gitignore",
    ".DS_Store",
    ".env",
    ".env.example",
    ".env.local",
    ".dockerignore",
    "db.sqlite3",
    "db.sqlite3-journal",
    "catalog.md",
    "Makefile",  # Windows 无法执行 make，改由 scripts/startup.py 替代
    "package.sh",  # 旧版 bash 打包脚本
    "package.py",  # 打包脚本自身
}

# 排除的文件扩展名
EXCLUDE_EXTS: set[str] = {
    ".pyc",
    ".pyo",
    ".log",
    ".zip",
    ".tar.gz",
}


def is_excluded(path: Path) -> bool:
    """判断文件是否应被排除"""
    name = path.name

    # 精确文件名匹配
    if name in EXCLUDE_FILES:
        return True

    # 扩展名匹配
    if path.suffix.lower() in EXCLUDE_EXTS:
        return True

    # *.egg-info/ 目录
    if name.endswith(".egg-info"):
        return True

    # static/css/dist/ 目录下的构建产物
    try:
        rel = path.relative_to(PROJECT_ROOT)
        parts = rel.parts
        if len(parts) >= 3 and parts[:3] == ("static", "css", "dist"):
            return True
    except ValueError:
        pass

    return False


# ── 核心打包逻辑 ──────────────────────────────────────────────────────────────


def build_package() -> Path:
    """执行打包，返回 zip 文件路径"""
    env_local = PROJECT_ROOT / ".env.local"
    if not env_local.exists():
        print("❌ 错误：缺少 .env.local 文件")
        print("   请先创建 .env.local（仅本地启动配置），打包时将自动生成为 .env")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = PROJECT_ROOT / "dist"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"{PROJECT_NAME}_{timestamp}.zip"

    # 创建临时暂存目录（退出时自动清理）
    staging_dir = Path(tempfile.mkdtemp())
    try:
        staging_root = staging_dir / PROJECT_NAME
        staging_root.mkdir()

        # 遍历项目目录，按规则复制文件
        for root, dirs, files in os.walk(PROJECT_ROOT):
            root_path = Path(root)

            # 过滤子目录（原地修改以阻止 os.walk 递归进入）
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not is_excluded(root_path / d)]

            for filename in files:
                file_path = root_path / filename

                if is_excluded(file_path):
                    continue

                rel = file_path.relative_to(PROJECT_ROOT)
                dest = staging_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest)

        # 将 .env.local 生成为 .env
        shutil.copy2(env_local, staging_root / ".env")

        # 打包为 zip（ZIP_DEFLATED 压缩）
        with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(staging_dir.rglob("*")):
                if file_path.is_file():
                    arcname = file_path.relative_to(staging_dir)
                    zf.write(file_path, arcname)
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    return output_file


# ── 输出结果 ──────────────────────────────────────────────────────────────────


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} B"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def main() -> None:
    output_file = build_package()
    file_size = output_file.stat().st_size

    print()
    print("✅ 打包完成")
    print(f"   📦 产物：{output_file}")
    print(f"   📏 大小：{format_size(file_size)}")
    print("   📄 .env.local → .env（已自动生成）")
    print()
    print("   排除内容：.git  .gitignore  docs/  deploy/  .github/  .qoder/  .trae/")
    print("             .env  .env.example  .env.local  Makefile  db.sqlite3  database/")
    print("             media/  logs/  node_modules/  static/css/dist/  staticfiles/")
    print("             .venv/  __pycache__/  .pytest_cache/  .ruff_cache/")
    print("             .screenshots/  temp/  dist/  scripts/package.py")
    print()


if __name__ == "__main__":
    main()
