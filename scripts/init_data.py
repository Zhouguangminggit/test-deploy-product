"""初始化项目基础数据。

用法（项目根目录）：
    uv run python scripts/init_data.py [--username admin] [--password admin123456] [--email admin@example.com]

说明：
- 幂等执行：超级用户已存在时跳过创建；
- 默认使用 dev 配置，可通过环境变量 DJANGO_SETTINGS_MODULE 覆盖；
- 后续业务模块（如字典、角色等）的基础数据可在此脚本中按模块追加。
"""

import argparse
import os
import sys
from pathlib import Path

# 保证直接执行脚本时项目根可导入（config / utils）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化项目基础数据（超级用户等）")
    parser.add_argument("--username", default="admin", help="管理员用户名（默认 admin）")
    parser.add_argument("--password", default="admin123456", help="管理员密码（默认 admin123456）")
    parser.add_argument("--email", default="admin@example.com", help="管理员邮箱")
    args = parser.parse_args()

    user_model = get_user_model()
    if user_model.objects.filter(username=args.username).exists():
        print(f"用户 {args.username} 已存在，跳过创建。")
        return

    user_model.objects.create_superuser(
        username=args.username,
        password=args.password,
        email=args.email,
    )
    print(f"超级用户已创建：{args.username} / {args.password}")
    print("可前往 /admin/ 登录后台。")


if __name__ == "__main__":
    main()
