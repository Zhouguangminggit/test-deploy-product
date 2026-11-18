import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from config.gunicorn_logging import AccessLogger

pytestmark = pytest.mark.skipif(
    os.name != "posix" or not shutil.which("sha256sum"),
    reason="部署脚本需要 POSIX shell 和 sha256sum",
)

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"


def test_compose_worker_and_beat_wait_for_web_healthcheck():
    services = yaml.safe_load((DEPLOY / "docker-compose.yml").read_text())["services"]
    probe = services["web"]["healthcheck"]["test"]
    assert probe[:3] == ["CMD", "python", "-c"]
    assert "/healthz/" in probe[3]
    assert "django-scaffold-healthcheck" in probe[3]
    for service in ("worker", "beat"):
        assert services[service]["depends_on"]["web"]["condition"] == "service_healthy"


@pytest.mark.parametrize(
    ("method", "path", "source", "agent", "status", "logged"),
    [
        ("GET", "/healthz/", "127.0.0.1", "django-scaffold-healthcheck", 200, False),
        ("GET", "/healthz/", "127.0.0.1", "django-scaffold-healthcheck", 503, True),
        ("GET", "/healthz/", "127.0.0.1", "curl", 200, True),
        ("GET", "/healthz/", "192.0.2.1", "django-scaffold-healthcheck", 200, True),
        ("GET", "/", "127.0.0.1", "django-scaffold-healthcheck", 200, True),
        ("POST", "/healthz/", "127.0.0.1", "django-scaffold-healthcheck", 200, True),
    ],
)
def test_gunicorn_omits_only_successful_internal_health_probes(
    method, path, source, agent, status, logged
):
    logger = AccessLogger.__new__(AccessLogger)
    response = SimpleNamespace(status_code=status)
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "REMOTE_ADDR": source,
        "HTTP_USER_AGENT": agent,
    }
    with patch("gunicorn.glogging.Logger.access", autospec=True) as access:
        logger.access(response, None, environ, None)
        if logged:
            access.assert_called_once_with(logger, response, None, environ, None)
        else:
            access.assert_not_called()


@pytest.fixture
def deploy(tmp_path):
    commands = tmp_path / "bin"
    commands.mkdir()
    docker_log = tmp_path / "docker.log"
    # Record Compose mutations without connecting to a Docker daemon. Production uses Linux flock.
    (commands / "docker").write_text('printf "%s\\n" "$*" >> "$DOCKER_LOG"\n')
    (commands / "flock").write_text("exit 0\n")
    for command in commands.iterdir():
        command.write_text("#!/bin/sh\n" + command.read_text())
        command.chmod(0o755)

    def run(target, port, repository="team/product", runtime=None):
        stage = tmp_path / "stage"
        stage.mkdir(exist_ok=True)
        (stage / "docker-compose.yml").write_text((DEPLOY / "docker-compose.yml").read_text())
        (stage / "compose.env").write_text(
            f"DEPLOY_REPOSITORY={repository}\nAPP_PORT={port}\nAPP_IMAGE=example.test/app:1\n"
        )
        runtime_path = stage / "runtime.env"
        runtime_path.unlink(missing_ok=True)
        if runtime is not None:
            runtime_path.write_text(runtime)
        (target / "deploy").mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            ["sh", DEPLOY / "apply.sh", stage, target],
            env={
                **os.environ,
                "PATH": f"{commands}:{os.environ['PATH']}",
                "DOCKER_LOG": str(docker_log),
            },
            capture_output=True,
            text=True,
            check=False,
        )

    return run, docker_log


def read_project(target):
    for line in (target / "deploy/.env").read_text().splitlines():
        key, _, value = line.partition("=")
        if key == "APP_COMPOSE_PROJECT":
            return value
    raise AssertionError("APP_COMPOSE_PROJECT is missing")


def test_deploy_isolates_directories_and_keeps_project_when_port_changes(deploy, tmp_path):
    run, docker_log = deploy
    first, second = tmp_path / "one/app", tmp_path / "two/app"
    for target in (first, second):
        (target / "deploy").mkdir(parents=True)
        (target / "deploy/.env.runtime").write_text("REDIS_URL=redis://legacy.test/0\n")
    result = run(first, 8101)
    assert result.returncode == 0, result.stderr
    first_project = read_project(first)

    result = run(second, 8102)
    assert result.returncode == 0, result.stderr
    second_project = read_project(second)
    assert second_project != first_project

    result = run(first, 8103)
    assert result.returncode == 0, result.stderr
    assert read_project(first) == first_project
    assert read_project(second) == second_project
    mutations = [line.split()[2] for line in docker_log.read_text().splitlines() if " up " in line]
    assert mutations == [first_project, second_project, first_project]


def test_deploy_refuses_to_replace_old_or_other_repository_configuration(deploy, tmp_path):
    run, docker_log = deploy
    target = tmp_path / "app"
    previous = target / "deploy/.env"
    previous.parent.mkdir(parents=True)
    previous.write_text("APP_PORT=8101\n")

    result = run(target, 8102)
    assert result.returncode != 0
    assert "旧版" in result.stderr
    assert previous.read_text() == "APP_PORT=8101\n"
    assert not docker_log.exists()

    previous.write_text("DEPLOY_REPOSITORY=team/previous\n")
    result = run(target, 8102)
    assert result.returncode != 0
    assert "已归属 team/previous" in result.stderr
    assert previous.read_text() == "DEPLOY_REPOSITORY=team/previous\n"
    assert not docker_log.exists()


def test_deploy_installs_managed_runtime_and_preserves_legacy_file(deploy, tmp_path):
    run, docker_log = deploy
    target = tmp_path / "app"
    result = run(target, 8102)
    assert result.returncode != 0
    assert "缺少生产运行配置" in result.stderr
    assert not docker_log.exists()

    legacy = target / "deploy/.env.runtime"
    legacy.write_text("LOG_LEVEL=INFO\n")
    runtime = "DATABASE_URL=mysql://test:fixture@mysql.test/catalog\n"

    result = run(target, 8102, runtime=runtime)
    assert result.returncode == 0, result.stderr
    managed = target / "deploy/.env.runtime.managed"
    assert managed.read_text() == runtime
    assert stat.S_IMODE(managed.stat().st_mode) == 0o600
    assert legacy.read_text() == "LOG_LEVEL=INFO\n"

    before = docker_log.read_text()
    result = run(target, 8102)
    assert result.returncode != 0
    assert "请提供完整" in result.stderr
    assert docker_log.read_text() == before
    assert managed.read_text() == runtime


def render_runtime(path, **values):
    return subprocess.run(
        [sys.executable, DEPLOY / "render-runtime-env.py", path],
        env=values,
        capture_output=True,
        text=True,
        check=False,
    )


def test_runtime_render_requires_complete_single_line_configuration(tmp_path):
    path = tmp_path / "runtime.env"
    assert render_runtime(path).returncode == 0
    assert not path.exists()

    result = render_runtime(path, REDIS_URL="redis://redis.test/0")
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr
    assert "MYSQL_DATABASE" in result.stderr
    assert not path.exists()

    result = render_runtime(
        path,
        SECRET_KEY="line-one\nline-two",
        REDIS_URL="redis://redis.test/0",
        DATABASE_URL="mysql://test:fixture@mysql.test/catalog",
    )
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr
    assert "line-one" not in result.stderr
    assert not path.exists()

    url = "mysql://test:fixture@mysql.test/catalog"
    result = render_runtime(
        path,
        SECRET_KEY="test-key",
        REDIS_URL="redis://redis.test/0",
        DATABASE_URL=url,
    )
    assert result.returncode == 0, result.stderr
    assert f"DATABASE_URL={url}" in path.read_text().splitlines()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_runtime_compose_preserves_credentials_and_overrides_legacy_url(tmp_path):
    if (
        not shutil.which("docker")
        or subprocess.run(
            ["docker", "compose", "version"], capture_output=True, check=False
        ).returncode
    ):
        pytest.skip("此检查需要 Docker Compose")

    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text((DEPLOY / "docker-compose.yml").read_text())
    (tmp_path / ".env.runtime").write_text(
        "DATABASE_URL=mysql://legacy@legacy.test/other\nLOG_LEVEL=WARNING\n"
    )
    password = "$test${KEEP_AS_LITERAL} # ' \" \\ "
    runtime = render_runtime(
        tmp_path / ".env.runtime.managed",
        SECRET_KEY="$literal-test-key",
        REDIS_URL="redis://redis.test/0",
        MYSQL_DATABASE="catalog",
        MYSQL_USER="catalog",
        MYSQL_PASSWORD=password,
        MYSQL_HOST="mysql.test",
    )
    assert runtime.returncode == 0, runtime.stderr
    config = subprocess.run(
        ["docker", "compose", "-f", compose_file, "config", "--format", "json"],
        env={
            "PATH": os.environ["PATH"],
            "APP_IMAGE": "example.test/app:1",
            "APP_COMPOSE_PROJECT": "deployment-test",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    services = yaml.safe_load(config.stdout)["services"]
    for name in ("web", "worker", "beat"):
        environment = services[name]["environment"]
        # Compose escapes dollar signs in exported config so it can be loaded again.
        assert environment["MYSQL_PASSWORD"].replace("$$", "$") == password
        assert environment["MYSQL_DATABASE"] == "catalog"
        assert environment["MYSQL_PORT"] == "3306"
        assert environment["SECRET_KEY"].replace("$$", "$") == "$literal-test-key"
        assert environment["REDIS_URL"] == "redis://redis.test/0"
        assert environment["DATABASE_URL"] == ""
        assert environment["LOG_LEVEL"] == "WARNING"
