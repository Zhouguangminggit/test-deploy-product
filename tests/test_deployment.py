import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.name != "posix" or not shutil.which("sha256sum"),
    reason="部署脚本需要 POSIX shell 和 sha256sum",
)

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"


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

    def run(target, port, repository="team/product"):
        stage = tmp_path / "stage"
        stage.mkdir(exist_ok=True)
        (stage / "docker-compose.yml").write_text((DEPLOY / "docker-compose.yml").read_text())
        (stage / "compose.env").write_text(
            f"DEPLOY_REPOSITORY={repository}\nAPP_PORT={port}\nAPP_IMAGE=example.test/app:1\n"
        )
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
