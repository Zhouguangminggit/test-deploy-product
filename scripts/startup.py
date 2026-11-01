#!/usr/bin/env python3
"""
一键启动脚本

自动完成：
  1. 检查 Python / uv / Node.js 环境
  2. 安装 Python 依赖（uv sync）
  3. 安装前端依赖并构建 CSS（可选，需 Node.js）
  4. 执行数据库迁移（makemigrations + migrate）
  5. 初始化基础数据（超级用户 admin / admin123456）
  6. 启动开发服务器

用法：
  python scripts/startup.py              # 完整启动
  python scripts/startup.py --skip-css   # 跳过 CSS 构建
  python scripts/startup.py --port 8080  # 指定端口

跨平台兼容 macOS / Linux / Windows。
"""

from __future__ import annotations

import argparse
import ctypes
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IS_WINDOWS = platform.system() == "Windows"
# uv sync 创建的虚拟环境 Python 路径（确保 manage.py 使用带依赖的解释器）
VENV_PYTHON = str(PROJECT_ROOT / (".venv/Scripts/python.exe" if IS_WINDOWS else ".venv/bin/python"))


# ── 命令行参数解析 ─────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="一键启动项目（跨平台）")
    parser.add_argument("--skip-css", action="store_true", help="跳过前端 CSS 构建（无需 Node.js）")
    parser.add_argument("--no-admin", action="store_true", help="跳过超级用户创建")
    parser.add_argument("--port", type=int, default=8000, help="开发服务器端口（默认 8000）")
    parser.add_argument("--host", default="127.0.0.1", help="开发服务器地址（默认 127.0.0.1）")
    return parser.parse_args()


# ── 工具函数 ──────────────────────────────────────────────────────────────────

_step_counter = 0


def step(msg: str) -> None:
    """打印带步骤编号的提示信息"""
    global _step_counter
    _step_counter += 1
    print(f"\n{'=' * 50}")
    print(f"  [{_step_counter}] {msg}")
    print(f"{'=' * 50}")


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    """执行命令并实时显示输出"""
    kwargs: dict = {
        "cwd": cwd or PROJECT_ROOT,
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
        kwargs["text"] = True
    else:
        kwargs.setdefault("stdout", None)
        kwargs.setdefault("stderr", None)

    # Windows 下 npm 命令可能需要 shell 解析（nvm 环境变量注入）
    use_shell = IS_WINDOWS and cmd and cmd[0] in ("npm", "npx")

    try:
        return subprocess.run(cmd, check=check, shell=use_shell, **kwargs)
    except FileNotFoundError:
        print(f"  ⚠️  命令不存在：{cmd[0]}")
        if check:
            sys.exit(1)
        return subprocess.CompletedProcess(cmd, returncode=1)
    except subprocess.CalledProcessError as e:
        if check:
            print(f"  ❌ 命令执行失败（退出码 {e.returncode}）")
            sys.exit(1)
        return subprocess.CompletedProcess(cmd, e.returncode)


def has_command(name: str) -> bool:
    """检查系统命令是否可用"""
    return shutil.which(name) is not None


def _find_npm_windows_paths() -> list[str]:
    """在 Windows 上搜索 nvm 管理的 npm/node 安装路径"""
    if not IS_WINDOWS:
        return []

    candidates: list[str] = []
    userprofile = os.environ.get("USERPROFILE", "")
    appdata = os.environ.get("APPDATA", "")

    # nvm-windows 默认安装目录
    nvm_dirs = [
        os.path.join(userprofile, "AppData", "Roaming", "nvm"),
        os.path.join(userprofile, ".nvm"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "nvm"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "nvm"),
    ]
    if appdata:
        nvm_dirs.append(os.path.join(appdata, "nvm"))

    for nvm_dir in nvm_dirs:
        nvm_path = Path(nvm_dir)
        if nvm_path.is_dir():
            # 遍历版本子目录，找到包含 npm 的最新版本
            for version_dir in sorted(nvm_path.iterdir(), reverse=True):
                if version_dir.is_dir():
                    npm_cmd = version_dir / ("npm.cmd" if IS_WINDOWS else "npm")
                    if npm_cmd.exists():
                        candidates.append(str(version_dir))
                        break

    return candidates


def _ensure_npm_available() -> bool:
    """确保 npm 可用，Windows 下自动检测 nvm 路径并注入 PATH"""
    if has_command("npm"):
        return True

    if IS_WINDOWS:
        nvm_paths = _find_npm_windows_paths()
        if nvm_paths:
            extra = os.pathsep.join(nvm_paths)
            os.environ["PATH"] = extra + os.pathsep + os.environ.get("PATH", "")
            if has_command("npm"):
                print(f"  ℹ️  已从 nvm 路径找到 npm：{nvm_paths[0]}")
                return True

    return False


def _check_windows_long_paths() -> bool:
    """检查 Windows 是否已启用长路径支持（>260 字符）"""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
        )
        value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
        winreg.CloseKey(key)
        return bool(value)
    except Exception:  # noqa: BLE001
        return False


def _ensure_windows_long_paths() -> None:
    """确保 Windows 启用长路径支持，否则 django-simpleui 等包含深层目录的包无法构建。

    自动尝试提权注册表修改；若用户拒绝 UAC 则打印手动操作指引并退出。
    """
    if _check_windows_long_paths():
        return

    print("\n  ⚠️  Windows 未启用长路径支持（>260 字符）")
    print("     django-simpleui 等包含深层目录的包需要此设置才能构建")
    print("     正在尝试自动启用（将弹出 UAC 管理员确认窗口）...\n")

    cmd = 'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f'
    shell32 = ctypes.windll.shell32
    # SW_HIDE = 0：隐藏提权窗口内容，仅保留 UAC 确认弹窗
    result = shell32.ShellExecuteW(None, "runas", "cmd.exe", f"/c {cmd}", None, 0)

    # ShellExecuteW 返回值 > 32 表示成功
    if result > 32 and _check_windows_long_paths():
        print("  ✅ Windows 长路径支持已启用")
        return

    # 自动启用失败，打印手动操作指引
    print("  ❌ 自动启用失败（可能拒绝了 UAC 提权）")
    print("     请以管理员身份打开 PowerShell，执行以下单行命令：")
    print()
    print(
        '     reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f'
    )
    print()
    print("     然后重新运行本脚本。")
    sys.exit(1)


# ── 各步骤实现 ────────────────────────────────────────────────────────────────


def check_prerequisites() -> None:
    """检查必要的环境依赖"""
    step("检查环境")

    # Python 版本
    py_version = platform.python_version()
    py_major, py_minor = sys.version_info[:2]
    print(f"  Python {py_version}")
    if py_major < 3 or (py_major == 3 and py_minor < 12):
        print("  ⚠️  项目要求 Python 3.12+，当前版本可能不兼容")
        print("     下载地址：https://www.python.org/downloads/")

    # uv
    if has_command("uv"):
        result = run_cmd(["uv", "--version"], capture=True, check=False)
        ver = result.stdout.strip() if result.returncode == 0 else "已安装"
        print(f"  uv {ver}")
    else:
        print("  ❌ 未找到 uv（Python 包管理器）")
        print("     安装方式：https://docs.astral.sh/uv/getting-started/installation/")
        sys.exit(1)

    # .env 文件
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        print("  .env 已就绪")
    else:
        print("  ⚠️  .env 文件不存在，将自动创建默认配置")
        env_local = PROJECT_ROOT / ".env.local"
        if env_local.exists():
            shutil.copy2(env_local, env_file)
            print("  ✅ 已从 .env.local 复制生成 .env")
        else:
            print("  ⚠️  .env.local 也不存在，将使用 Django 默认配置")

    # Node.js（仅警告，不阻断）
    if has_command("node"):
        result = run_cmd(["node", "--version"], capture=True, check=False)
        ver = result.stdout.strip() if result.returncode == 0 else "已安装"
        print(f"  Node.js {ver}")
        # 检查 npm（Windows 下自动探测 nvm 路径）
        if _ensure_npm_available():
            result = run_cmd(["npm", "--version"], capture=True, check=False)
            npm_ver = result.stdout.strip() if result.returncode == 0 else "已安装"
            print(f"  npm {npm_ver}")
        else:
            print("  ⚠️  npm 未找到（如使用 nvm 管理 Node.js，请确认已 nvm use <version>）")
    else:
        print("  ℹ️  未检测到 Node.js，CSS 构建将跳过（不影响后端启动）")

    # Windows 长路径检查（django-simpleui 构建需要）
    if IS_WINDOWS:
        _ensure_windows_long_paths()


def install_python_deps() -> None:
    """安装 Python 依赖"""
    step("安装 Python 依赖")
    run_cmd(["uv", "sync"])
    print("  ✅ Python 依赖安装完成")


def build_css() -> None:
    """安装前端依赖并构建 CSS"""
    step("构建前端 CSS")

    if not has_command("node"):
        print("  ⚠️  Node.js 未安装，跳过 CSS 构建")
        print("     页面样式可能不完整，但不影响后端功能")
        return

    if not _ensure_npm_available():
        print("  ⚠️  npm 未找到，跳过 CSS 构建")
        if IS_WINDOWS:
            print("     如使用 nvm-windows 管理 Node.js，请先执行：nvm use <version>")
        print("     页面样式可能不完整，但不影响后端功能")
        return

    # 确保产物目录存在
    dist_dir = PROJECT_ROOT / "static" / "css" / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    # 安装前端依赖
    run_cmd(["npm", "install"])
    print("  ✅ npm 依赖安装完成")

    # 直接调用 node_modules 中的 tailwindcss CLI，
    # 绕开 npm scripts 中 mkdir -p / if not exist 的跨平台 shell 兼容问题
    input_css = PROJECT_ROOT / "static" / "css" / "base.css"
    output_css = dist_dir / "base.css"
    tw_cli = (
        PROJECT_ROOT
        / "node_modules"
        / ".bin"
        / ("tailwindcss.cmd" if IS_WINDOWS else "tailwindcss")
    )

    if tw_cli.exists():
        run_cmd(
            [
                str(tw_cli),
                "-i",
                str(input_css),
                "-o",
                str(output_css),
                "--minify",
            ]
        )
    else:
        # 回退到 npm scripts
        build_cmd = "build:win" if IS_WINDOWS else "build"
        run_cmd(["npm", "run", build_cmd])

    # 验证产物
    if output_css.exists() and output_css.stat().st_size > 0:
        print(f"  ✅ CSS 构建完成 → {output_css.relative_to(PROJECT_ROOT)}")
    else:
        print("  ⚠️  CSS 产物未生成，页面样式将缺失")
        print("     可手动执行：npm install && npm run build")


def run_migrations() -> None:
    """执行数据库迁移"""
    step("数据库迁移")

    manage = [VENV_PYTHON, "manage.py"]

    # makemigrations：检测模型变更生成迁移文件
    run_cmd([*manage, "makemigrations"], check=False)

    # migrate：应用迁移到数据库
    run_cmd([*manage, "migrate"])
    print("  ✅ 数据库迁移完成")


def init_data(no_admin: bool) -> None:
    """初始化基础数据（超级用户等）"""
    if no_admin:
        print("\n  ℹ️  跳过超级用户创建（--no-admin）")
        return

    step("初始化基础数据")

    init_script = PROJECT_ROOT / "scripts" / "init_data.py"
    if init_script.exists():
        run_cmd([VENV_PYTHON, str(init_script)])
        print("  ✅ 基础数据初始化完成")
        print("     管理员账号：admin / admin123456")
    else:
        print("  ⚠️  scripts/init_data.py 不存在，跳过初始化")


def start_server(host: str, port: int) -> None:
    """启动开发服务器"""
    step(f"启动开发服务器 → http://{host}:{port}")

    print("\n  🚀 服务器即将启动，按 Ctrl+C 停止\n")

    manage = [VENV_PYTHON, "manage.py"]
    run_cmd([*manage, "runserver", f"{host}:{port}"], check=False)


# ── 主流程 ────────────────────────────────────────────────────────────────────


def _read_site_name() -> str:
    """从 .env 或 .env.local 读取 SITE_NAME，用于启动横幅显示"""
    for env_file in (PROJECT_ROOT / ".env", PROJECT_ROOT / ".env.local"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("SITE_NAME="):
                    return line.split("=", 1)[1].strip()
    return "项目"


def main() -> None:
    site_name = _read_site_name()
    title = f"{site_name} 一键启动工具"
    # 中文字符占两个显示宽度，用 ljust 补齐方框
    padded = title + " " * max(0, 42 - sum(2 if ord(c) > 127 else 1 for c in title))
    print()
    print(f"  ╔{'═' * 46}╗")
    print(f"  ║  {padded}  ║")
    print(f"  ╚{'═' * 46}╝")
    print()

    args = parse_args()

    try:
        check_prerequisites()
        install_python_deps()

        if not args.skip_css:
            build_css()
        else:
            print("\n  ℹ️  跳过 CSS 构建（--skip-css）")

        run_migrations()
        init_data(no_admin=args.no_admin)
        start_server(host=args.host, port=args.port)

    except KeyboardInterrupt:
        print("\n\n  👋 已停止")
        sys.exit(0)


if __name__ == "__main__":
    main()
