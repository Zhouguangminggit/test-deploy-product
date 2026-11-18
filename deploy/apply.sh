#!/bin/sh
# 由流水线在目标服务器执行。参数是本次上传的独立暂存目录和部署目录。
set -eu

stage=$(cd "$1" && pwd -P)
cd "$2"
deployment=$(pwd -P)
exec 9>deploy/.lock
flock -x 9

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

# 不读取已有 dotenv 内容为 shell 脚本。旧部署需核对容器及媒体卷后再切换。
repository=$(sed -n 's/^DEPLOY_REPOSITORY=//p' "$stage/compose.env")
[ -n "$repository" ] || fail "缺少部署仓库标识"
if [ -f deploy/.env ]; then
    previous_repository=$(sed -n 's/^DEPLOY_REPOSITORY=//p' deploy/.env)
    [ -n "$previous_repository" ] || fail "检测到旧版 deploy/.env，请按生产部署文档完成旧项目切换"
    [ "$previous_repository" = "$repository" ] || fail "部署目录已归属 ${previous_repository}，请为 $repository 配置独立的 DEPLOY_PATH"
fi

port=$(sed -n 's/^APP_PORT=//p' "$stage/compose.env")
case "$port" in
    ""|0*|*[!0-9]*) fail "APP_PORT 必须是 1 至 65535 的十进制整数" ;;
esac
[ "${#port}" -le 5 ] && [ "$port" -le 65535 ] || fail "APP_PORT 必须是 1 至 65535"

hash=$(printf '%s' "$deployment" | sha256sum)
project="scaffold-$(printf '%.20s' "$hash")"
printf 'APP_COMPOSE_PROJECT=%s\n' "$project" >> "$stage/compose.env"

# 显式固定项目和配置文件。清除同名 shell 变量，避免覆盖发布文件。
unset APP_IMAGE APP_PORT ALLOWED_HOSTS PIXABAY_API_KEY SITE_LOGO APP_COMPOSE_PROJECT APP_MANAGED_ENV_FILE
export APP_COMPOSE_PROJECT="$project"
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

compose "$stage/compose.env" "$stage/docker-compose.yml" config --quiet
compose "$stage/compose.env" "$stage/docker-compose.yml" pull
cp "$stage/docker-compose.yml" deploy/docker-compose.yml.new
cp "$stage/compose.env" deploy/.env.new
chmod 600 deploy/.env.new
if [ -f "$stage/runtime.env" ]; then
    install -m 600 "$stage/runtime.env" deploy/.env.runtime.managed.new
    mv deploy/.env.runtime.managed.new deploy/.env.runtime.managed
fi
unset APP_MANAGED_ENV_FILE
mv deploy/docker-compose.yml.new deploy/docker-compose.yml
mv deploy/.env.new deploy/.env

if ! compose deploy/.env deploy/docker-compose.yml up -d --pull never --wait --wait-timeout 180; then
    compose deploy/.env deploy/docker-compose.yml ps -a
    compose deploy/.env deploy/docker-compose.yml logs --tail=100
    exit 1
fi
