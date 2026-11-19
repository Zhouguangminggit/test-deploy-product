#!/bin/sh
# 由流水线在目标服务器执行。参数是本次上传的独立暂存目录和部署目录。
set -eu

stage=$(cd "$1" && pwd -P)
cd "$2"
deployment=$(pwd -P)
. "$stage/runtime-common.sh"
umask 077

# 不读取已有 dotenv 内容为 shell 脚本。旧部署需核对容器及媒体卷后再切换。
repository=$(dotenv_value DEPLOY_REPOSITORY "$stage/compose.env")
[ -n "$repository" ] || fail "缺少部署仓库标识"
host_lock 180
product_lock deploy/.lock
mode=$(dotenv_value APP_DEPLOY_MODE "$stage/compose.env")
if [ -f deploy/.env ]; then
    previous_repository=$(dotenv_value DEPLOY_REPOSITORY deploy/.env)
    [ -n "$previous_repository" ] || fail "检测到旧版 deploy/.env，请按生产部署文档完成旧项目切换"
    [ "$previous_repository" = "$repository" ] || fail "部署目录已归属 ${previous_repository}，请为 $repository 配置独立的 DEPLOY_PATH"
    previous_mode=$(dotenv_value APP_DEPLOY_MODE deploy/.env)
    mode=${mode:-${previous_mode:-scheduled}}
fi
mode=${mode:-web}
case "$mode" in
    web) profiles= ;;
    worker) profiles=worker ;;
    scheduled) profiles=worker,scheduled ;;
    *) fail "APP_DEPLOY_MODE 必须为 web、worker 或 scheduled" ;;
esac

port=$(dotenv_value APP_PORT "$stage/compose.env")
case "$port" in
    ""|0*|*[!0-9]*) fail "APP_PORT 必须是 1 至 65535 的十进制整数" ;;
esac
[ "${#port}" -le 5 ] && [ "$port" -le 65535 ] || fail "APP_PORT 必须是 1 至 65535"

hash=$(printf '%s' "$deployment" | sha256sum)
project="scaffold-$(printf '%.20s' "$hash")"
sed '/^APP_DEPLOY_MODE=/d' "$stage/compose.env" > "$stage/effective.env"
printf 'APP_COMPOSE_PROJECT=%s\nAPP_DEPLOY_MODE=%s\nCOMPOSE_PROFILES=%s\n' \
    "$project" "$mode" "$profiles" >> "$stage/effective.env"

# 显式固定项目和配置文件。清除同名 shell 变量，避免覆盖发布文件。
reset_compose_environment
compose() {
    env_file=$1
    compose_file=$2
    shift 2
    docker compose -p "$project" --project-directory "$deployment/deploy" \
        --env-file "$env_file" -f "$compose_file" "$@"
}

if [ -f "$stage/runtime.env" ]; then
    export APP_MANAGED_ENV_FILE="$stage/runtime.env"
elif [ -f deploy/.env.runtime.managed ]; then
    fail "当前部署由中台管理运行配置，请提供完整的生产运行配置"
elif [ ! -f deploy/.env.runtime ]; then
    fail "缺少生产运行配置，请在中台或 GitHub Secrets 中配置"
fi

if [ "$mode" = web ]; then
    compose "$stage/effective.env" "$stage/docker-compose.yml" config --quiet
else
    config=$(compose "$stage/effective.env" "$stage/docker-compose.yml" config --format json)
    printf '%s' "$config" | python3 -c '
import json
import sys

worker = json.load(sys.stdin)["services"]["worker"]
if not (worker.get("environment", {}).get("REDIS_URL") or "").strip():
    sys.exit("worker 和 scheduled 模式要求提供 REDIS_URL")
'
fi

seed_jobs_running
compose "$stage/effective.env" "$stage/docker-compose.yml" pull
# Disabled profiles do not stop containers from an earlier release. Explicitly
# remove only these services in the current Compose project, keeping its volumes.
case "$mode" in
    web)
        compose "$stage/effective.env" "$stage/docker-compose.yml" \
            --profile worker --profile scheduled rm --stop --force beat worker
        ;;
    worker)
        compose "$stage/effective.env" "$stage/docker-compose.yml" \
            --profile worker --profile scheduled rm --stop --force beat
        ;;
esac
cp "$stage/docker-compose.yml" deploy/docker-compose.yml.new
cp "$stage/effective.env" deploy/.env.new
chmod 600 deploy/.env.new
install -m 600 "$stage/runtime-common.sh" deploy/runtime-common.sh.new
install -m 600 "$stage/product-runtime.sh" deploy/product-runtime.sh.new
if [ -f "$stage/runtime.env" ]; then
    install -m 600 "$stage/runtime.env" deploy/.env.runtime.managed.new
    mv deploy/.env.runtime.managed.new deploy/.env.runtime.managed
fi
unset APP_MANAGED_ENV_FILE
mv deploy/docker-compose.yml.new deploy/docker-compose.yml
mv deploy/.env.new deploy/.env
mv deploy/runtime-common.sh.new deploy/runtime-common.sh
mv deploy/product-runtime.sh.new deploy/product-runtime.sh

if ! compose deploy/.env deploy/docker-compose.yml up -d --pull never --wait --wait-timeout 180; then
    compose deploy/.env deploy/docker-compose.yml ps -a
    compose deploy/.env deploy/docker-compose.yml logs --tail=100
    exit 1
fi
