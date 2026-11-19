"""Internal commands used by the deployed one-off seedkit runner."""

from django.core.management.base import BaseCommand, CommandError

from apps.seedkit.enums import SeedRunStatus
from apps.seedkit.services import create_run, execute_run_by_id, fail_interrupted_run


class Command(BaseCommand):
    help = "登记、执行或收尾单次容器初始化"

    def add_arguments(self, parser) -> None:
        actions = parser.add_subparsers(dest="action", required=True)
        actions.add_parser("create")
        execute = actions.add_parser("execute")
        execute.add_argument("run_id", type=int)
        fail = actions.add_parser("fail")
        fail.add_argument("run_id", type=int)
        fail.add_argument("message")

    def handle(self, *args, action, **options) -> None:
        if action == "create":
            self.stdout.write(str(create_run().pk))
            return
        if action == "fail":
            fail_interrupted_run(options["run_id"], options["message"])
            return
        run = execute_run_by_id(options["run_id"])
        if run.status == SeedRunStatus.FAILED:
            raise CommandError("数据初始化失败，详见运行日志")
