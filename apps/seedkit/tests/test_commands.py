"""seedkit 管理命令测试（stdout JSON 契约，供中台 SSH 解析）。

覆盖：
- seedkit_run --sync 成功输出 JSON 且写库；失败先输出 failed JSON 再抛 CommandError；
- seedkit_run 异步路径输出 task_id 并回填 celery_task_id（mock 投递，不依赖 broker）；
  投递失败落库 failed 并抛 CommandError；
- seedkit_status 输出最近/指定运行的完整 JSON（含 logs），--tail 截断，缺失记录报错。
"""

import json
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.seedkit.enums import SeedRunStatus
from apps.seedkit.models import SeedRun


def _marketplace_yaml():
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


def _last_json(out: StringIO) -> dict:
    """解析命令 stdout 的最后一行 JSON（过程日志走 stderr，不污染 stdout）。"""
    return json.loads(out.getvalue().strip().splitlines()[-1])


@pytest.mark.django_db
def test_seedkit_run_sync_success(yaml_config, seedkit_tables):
    """--sync：同步执行并输出 run_id/status/统计。"""
    yaml_config(_marketplace_yaml())
    out = StringIO()

    call_command("seedkit_run", "--trigger", "local", "--sync", stdout=out)
    payload = _last_json(out)

    assert payload["status"] == SeedRunStatus.SUCCESS
    assert payload["created"] == 4
    assert payload["error"] is None
    assert SeedRun.objects.get(pk=payload["run_id"]).status == SeedRunStatus.SUCCESS


@pytest.mark.django_db
def test_seedkit_run_sync_failure_emits_json_then_raises(yaml_config, seedkit_tables):
    """--sync 失败：先输出 failed JSON，再抛 CommandError（非零退出码）。"""
    yaml_config(
        {"version": 1, "modules": {"m": {"models": [{"model": "seedkit.Nope", "rows": []}]}}}
    )
    out = StringIO()

    with pytest.raises(CommandError):
        call_command("seedkit_run", "--sync", stdout=out)

    payload = _last_json(out)
    assert payload["status"] == SeedRunStatus.FAILED
    assert payload["error"]


@pytest.mark.django_db
def test_seedkit_run_async_emits_task_id(yaml_config, seedkit_tables, monkeypatch):
    """异步路径：投递 Celery 后输出 task_id 并回填 celery_task_id（mock，不连 broker）。"""
    yaml_config(_marketplace_yaml())
    calls: list[int] = []

    class _AsyncResult:
        id = "task-abc"

    class _FakeTask:
        def delay(self, run_id):
            calls.append(run_id)
            return _AsyncResult()

    monkeypatch.setattr("apps.seedkit.management.commands.seedkit_run.run_seedkit", _FakeTask())
    out = StringIO()

    call_command("seedkit_run", stdout=out)  # 缺省异步
    payload = _last_json(out)

    assert payload["status"] == SeedRunStatus.PENDING
    assert payload["task_id"] == "task-abc"
    run = SeedRun.objects.get(pk=payload["run_id"])
    assert run.celery_task_id == "task-abc"
    assert calls == [run.pk]


@pytest.mark.django_db
def test_seedkit_run_async_delivery_failure(yaml_config, seedkit_tables, monkeypatch):
    """投递失败（broker 不可达）：落库 failed、输出错误 JSON 并抛 CommandError。"""
    yaml_config(_marketplace_yaml())

    class _BoomTask:
        def delay(self, run_id):
            raise RuntimeError("redis 不可达")

    monkeypatch.setattr("apps.seedkit.management.commands.seedkit_run.run_seedkit", _BoomTask())
    out = StringIO()

    with pytest.raises(CommandError):
        call_command("seedkit_run", stdout=out)

    payload = _last_json(out)
    assert payload["status"] == SeedRunStatus.FAILED
    run = SeedRun.objects.get(pk=payload["run_id"])
    assert run.status == SeedRunStatus.FAILED
    assert "投递失败" in run.error_message


@pytest.mark.django_db
def test_seedkit_status_latest(yaml_config, seedkit_tables):
    """缺省查询最近一次运行，返回状态/统计与日志明细。"""
    yaml_config(_marketplace_yaml())
    call_command("seedkit_run", "--sync", stdout=StringIO())

    out = StringIO()
    call_command("seedkit_status", stdout=out)
    payload = _last_json(out)

    assert payload["status"] == SeedRunStatus.SUCCESS
    assert payload["created"] == 4
    assert payload["logs"]
    assert {"level", "message", "at"} <= set(payload["logs"][0])


@pytest.mark.django_db
def test_seedkit_status_by_run_id_and_tail(yaml_config, seedkit_tables):
    """--run-id 指定运行、--tail 截断日志。"""
    yaml_config(_marketplace_yaml())
    run_out = StringIO()
    call_command("seedkit_run", "--sync", stdout=run_out)
    run_id = _last_json(run_out)["run_id"]

    out = StringIO()
    call_command("seedkit_status", "--run-id", str(run_id), "--tail", "1", stdout=out)
    payload = _last_json(out)

    assert payload["run_id"] == run_id
    assert len(payload["logs"]) == 1


@pytest.mark.django_db
def test_seedkit_status_missing_run_raises():
    """指定不存在的 run-id → CommandError。"""
    with pytest.raises(CommandError):
        call_command("seedkit_status", "--run-id", "999999", stdout=StringIO())


@pytest.mark.django_db
def test_seedkit_status_no_runs_raises():
    """无任何运行记录时缺省查询 → CommandError。"""
    with pytest.raises(CommandError):
        call_command("seedkit_status", stdout=StringIO())


@pytest.mark.django_db
def test_seedkit_job_create_execute_and_preserve_terminal_result(yaml_config, seedkit_tables):
    yaml_config(_marketplace_yaml())
    out = StringIO()
    call_command("seedkit_job", "create", stdout=out)
    run_id = out.getvalue().strip()
    assert SeedRun.objects.get(pk=run_id).status == SeedRunStatus.PENDING

    call_command("seedkit_job", "execute", run_id)
    call_command("seedkit_job", "fail", run_id, "容器退出")
    run = SeedRun.objects.get(pk=run_id)
    assert run.status == SeedRunStatus.SUCCESS
    assert run.created_count == 4
    assert not run.error_message


@pytest.mark.django_db
@pytest.mark.parametrize("status", [SeedRunStatus.PENDING, SeedRunStatus.RUNNING])
def test_seedkit_job_records_interruption_once(status):
    run = SeedRun.objects.create(status=status)
    call_command("seedkit_job", "fail", str(run.pk), "初始化容器超出内存上限")
    call_command("seedkit_job", "fail", str(run.pk), "重复收尾")
    run.refresh_from_db()

    assert run.status == SeedRunStatus.FAILED
    assert run.finished_at is not None
    assert run.error_message == "初始化容器超出内存上限"
    assert list(run.logs.values_list("message", flat=True)) == [run.error_message]
