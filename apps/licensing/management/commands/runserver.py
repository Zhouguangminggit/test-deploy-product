"""确保开发静态文件请求也经过授权中间件。"""

from django.contrib.staticfiles.management.commands.runserver import Command as StaticCommand


class Command(StaticCommand):
    def get_handler(self, *args, **options):
        options["use_static_handler"] = False
        return super().get_handler(*args, **options)
