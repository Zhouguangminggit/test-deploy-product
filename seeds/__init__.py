"""种子数据配置自动发现。

扫描 seeds/ 目录下所有 .py 文件（排除 _ 前缀和 __init__.py），
导入并收集每个文件中的 MODULE 字典，供 seed_data.py 主入口统一调度。

新增业务模块只需在 seeds/ 下创建配置文件并定义 MODULE 即可被自动发现。
"""

import importlib
import sys
from pathlib import Path

from loguru import logger

SEEDS_DIR = Path(__file__).resolve().parent


def discover_modules() -> list[dict]:
    """扫描并加载 seeds/ 目录下所有模块配置。

    Returns:
        MODULE 字典列表，每个元素包含 name / description / dependencies / models。
        加载失败的文件会打印警告并跳过，不影响其他模块。
    """
    modules = []

    for py_file in sorted(SEEDS_DIR.glob("*.py")):
        # 跳过 __init__.py 和 _ 前缀的模板/工具文件
        if py_file.name.startswith("_") or py_file.name == "__init__.py":
            continue

        module_name = py_file.stem
        full_module_name = f"seeds.{module_name}"

        try:
            # 动态导入
            if full_module_name in sys.modules:
                mod = sys.modules[full_module_name]
            else:
                spec = importlib.util.spec_from_file_location(full_module_name, py_file)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[full_module_name] = mod
                spec.loader.exec_module(mod)

            if hasattr(mod, "MODULE"):
                config = mod.MODULE
                if "name" not in config:
                    config["name"] = module_name
                modules.append(config)
                logger.debug("已加载种子配置: {} ({})", config.get("name"), py_file.name)
            else:
                logger.warning("种子文件 {} 缺少 MODULE 变量，已跳过", py_file.name)

        except Exception as exc:
            logger.error("加载种子文件 {} 失败: {}", py_file.name, exc)

    return modules


def list_module_names() -> list[str]:
    """返回所有已发现模块的 name 列表（用于 CLI 展示）。"""
    return [m.get("name", "unknown") for m in discover_modules()]
