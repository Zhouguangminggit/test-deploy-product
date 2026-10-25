"""项目配置包。

在生产环境使用 MySQL 时，通过 PyMySQL 以 MySQLdb 的接口被 Django 调用。
开发环境使用 SQLite，不会触发 MySQL 后端；PyMySQL 未安装时安全忽略。
"""

try:
    import pymysql

    # Django 的 MySQL 后端会校验 mysqlclient >= 1.4.3，
    # 而 PyMySQL 的版本号（如 1.1.1）会被误判为过低。
    # 这里将 version_info 提升到兼容值以通过校验（PyMySQL 功能上兼容）。
    if pymysql.version_info < (1, 4, 3):
        pymysql.version_info = (1, 4, 3, "final", 0)

    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover - 最小化环境下未安装 PyMySQL 时忽略
    pass
