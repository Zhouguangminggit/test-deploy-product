#!/bin/sh
# Installed alongside the active Compose publication. Called via SSH using sh.
set -eu
cd "$(dirname "$0")"
. ./runtime-common.sh
reset_compose_environment

load_project() {
    [ -r .env ] || fail "无法读取 deploy/.env"
    project=$(dotenv_value APP_COMPOSE_PROJECT .env)
    case "$project" in
        ''|[!a-z0-9]*|*[!a-z0-9_-]*) fail "deploy/.env 中的 APP_COMPOSE_PROJECT 格式无效" ;;
    esac
    mode=$(dotenv_value APP_DEPLOY_MODE .env)
}

compose() {
    docker compose -p "$project" --env-file .env -f docker-compose.yml "$@"
}

manage() {
    compose exec -T web python manage.py "$@"
}

validate_run_id() {
    case "$1" in
        ''|0*|*[!0-9]*) fail "无效的初始化运行 ID" ;;
    esac
}

finish_job() {
    job_id=$1
    job_name=$project-seedkit-$job_id
    existing=$(docker ps -a -q --filter "name=^/$job_name\$" \
        --filter "label=com.docker.compose.project=$project" \
        --filter "label=org.django-scaffold.seedkit-run=$job_id") ||
        fail "无法查询初始化容器"
    [ -n "$existing" ] || return 0
    # A concurrent status reader may already have removed the stopped container.
    state=$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}} {{.State.OOMKilled}}' \
        "$existing") || return 0
    case "$state" in
        'exited '*|created\ *|dead\ *) ;;
        *) return 0 ;;
    esac
    case "$state" in
        *' true') reason="初始化容器超出内存上限" ;;
        'exited 124 '*|'exited 137 '*) reason="初始化容器超时或被强制终止" ;;
        *) reason="初始化容器提前退出（${state}）" ;;
    esac
    manage seedkit_job fail "$job_id" "$reason"
    docker rm "$existing" >/dev/null 2>&1 ||
        [ -z "$(docker ps -aq --filter "id=$existing")" ] ||
        fail "无法清理已退出的初始化容器"
}

finish_stopped_jobs() {
    finished=$(docker ps -a --filter "label=com.docker.compose.project=$project" \
        --filter label=org.django-scaffold.seedkit-run \
        --filter status=created --filter status=exited --filter status=dead \
        --format '{{.Label "org.django-scaffold.seedkit-run"}}') ||
        fail "无法查询已停止的初始化容器"
    for job in $finished; do
        validate_run_id "$job"
        finish_job "$job"
    done
}

action=$1
shift
case "$action" in
    start)
        host_lock 0
        product_lock .lock
        load_project
        seed_jobs_running
        compose up -d --wait --wait-timeout "$1"
        ;;
    stop)
        host_lock 0
        product_lock .lock
        load_project
        seed_jobs_running --filter "label=com.docker.compose.project=$project"
        finish_stopped_jobs
        compose --profile worker --profile scheduled --profile seedkit down
        ;;
    seed-trigger)
        host_lock 0
        product_lock .lock
        load_project
        if [ "$mode" != web ]; then
            manage seedkit_run --trigger platform
            exit
        fi
        seed_jobs_running
        finish_stopped_jobs
        run_id=$(manage seedkit_job create)
        validate_run_id "$run_id"
        if ! compose run -d --no-deps --pull never --name "$project-seedkit-$run_id" \
            --label "org.django-scaffold.seedkit-run=$run_id" seedkit \
            timeout --kill-after=5s 830s python manage.py seedkit_job execute "$run_id" >/dev/null; then
            # Compose can fail after creating the container. Keep any live job
            # visible to polling instead of overriding its result.
            live=$(docker ps --filter "name=^/$project-seedkit-$run_id\$" --format '{{.ID}}') ||
                fail "无法检查初始化容器启动结果"
            if [ -z "$live" ]; then
                manage seedkit_job fail "$run_id" "启动初始化容器失败"
                finish_job "$run_id"
                manage seedkit_status --run-id "$run_id"
                exit 1
            fi
        fi
        printf '{"run_id":%s,"status":"pending"}\n' "$run_id"
        ;;
    seed-status)
        validate_run_id "$1"
        load_project
        finish_job "$1"
        manage seedkit_status --run-id "$1" --tail 50
        ;;
    *) fail "未知的产品运行操作" ;;
esac
