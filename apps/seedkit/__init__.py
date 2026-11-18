"""seedkit 数据初始化基座模块。

统一 YAML 配置（seeds/seed_data.yml）驱动业务数据初始化：本地脚本与线上中台
触发加载同一份配置，通过 SSH + Celery 异步执行，运行记录与日志落库可追溯。
"""
