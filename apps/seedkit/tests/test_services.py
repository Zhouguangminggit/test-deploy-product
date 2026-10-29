"""seedkit.services 运行编排测试（状态流转 + 日志落库）。

覆盖：create_run 初始态、execute_run 成功/配置失败/部分成功、空配置视为成功、
execute_run_by_id 入口，以及 RunLogger 双写（SeedRunLog 落库可追溯）。
配置统一走 yaml_config 夹具指向临时 SEEDKIT_CONFIG，数据写入依赖 seedkit_tables。
"""

import pytest

from apps.seedkit.enums import SeedLogLevel, SeedRunStatus, SeedTrigger
from apps.seedkit.models import SeedRun, SeedRunLog
from apps.seedkit.services import create_run, execute_run, execute_run_by_id


def _marketplace_yaml():
    """分类（电子器材/图书）+ 商品两级 FK（无图片，聚焦状态流转）。"""
    return {
        "version": 1,
        "modules": {
            "products": {
                "models": [
                    {
                        "model": "seedkit.SeedCategory",
                        "rows": [{"name": "电子器材"}, {"name": "图书"}],
                    },
                    {
                        "model": "seedkit.SeedProduct",
                        "rows": [
                            {"title": "手机", "category": {"ref": "seedkit.SeedCategory.电子器材"}},
                            {"title": "书籍", "category": {"ref": "seedkit.SeedCategory.图书"}},
                        ],
                    },
                ]
            }
        },
    }


@pytest.mark.django_db
def test_create_run_defaults_pending():
    """create_run 只登记不执行，初始为 pending。"""
    run = create_run()
    assert run.pk
    assert run.status == SeedRunStatus.PENDING
    assert run.trigger == SeedTrigger.PLATFORM
    assert run.modules == []
    assert run.refresh is False


@pytest.mark.django_db
def test_execute_run_success(yaml_config, seedkit_tables):
    """成功：状态置 success、统计回填、起止时间落库、过程日志可追溯。"""
    yaml_config(_marketplace_yaml())
    run = create_run(modules=None, refresh=False, trigger=SeedTrigger.LOCAL)

    result = execute_run(run)

    assert result.status == SeedRunStatus.SUCCESS
    assert result.created_count == 4  # 2 分类 + 2 商品
    assert result.skipped_count == 0
    assert result.error_message == ""
    assert result.started_at and result.finished_at
    # 落库复查（确保 save 生效，而非仅内存对象）
    assert SeedRun.objects.get(pk=result.pk).status == SeedRunStatus.SUCCESS
    messages = list(SeedRunLog.objects.filter(run=result).values_list("message", flat=True))
    assert any("开始初始化" in m for m in messages)
    assert any("初始化完成" in m for m in messages)


@pytest.mark.django_db
def test_execute_run_empty_config_is_success(yaml_config, seedkit_tables):
    """空 YAML（无业务模块）视为成功、零统计，而非失败。"""
    yaml_config({"version": 1, "modules": {}})
    run = create_run()

    result = execute_run(run)

    assert result.status == SeedRunStatus.SUCCESS
    assert result.created_count == 0


@pytest.mark.django_db
def test_execute_run_config_error_fails(yaml_config, seedkit_tables):
    """loader fail-fast（未知模型）→ 运行置 failed 并记 error 日志。"""
    yaml_config(
        {"version": 1, "modules": {"m": {"models": [{"model": "seedkit.Nope", "rows": []}]}}}
    )
    run = create_run()

    result = execute_run(run)

    assert result.status == SeedRunStatus.FAILED
    assert "配置校验失败" in result.error_message
    assert SeedRunLog.objects.filter(run=result, level=SeedLogLevel.ERROR).exists()


@pytest.mark.django_db
def test_execute_run_partial(yaml_config, seedkit_tables):
    """一个模块成功、一个运行期失败 → 状态 partial，保留成功部分统计。"""
    yaml_config(
        {
            "version": 1,
            "modules": {
                # cats 声明在前（正常），bad 商品引用不存在分类（运行期失败）
                "cats": {
                    "models": [
                        {"model": "seedkit.SeedCategory", "rows": [{"name": "电子器材"}]},
                    ]
                },
                "bad": {
                    "models": [
                        {
                            "model": "seedkit.SeedProduct",
                            "rows": [
                                {
                                    "title": "手机",
                                    "category": {"ref": "seedkit.SeedCategory.幽灵"},
                                }
                            ],
                        }
                    ]
                },
            },
        }
    )
    run = create_run()

    result = execute_run(run)

    assert result.status == SeedRunStatus.PARTIAL
    assert "bad" in result.error_message
    assert result.created_count == 1  # cats 成功写入 1 条


@pytest.mark.django_db
def test_execute_run_by_id(yaml_config, seedkit_tables):
    """Celery 入口：按主键取记录并执行。"""
    yaml_config(_marketplace_yaml())
    run = create_run(trigger=SeedTrigger.PLATFORM)

    result = execute_run_by_id(run.pk)

    assert result.pk == run.pk
    assert result.status == SeedRunStatus.SUCCESS
