# Shared by the release and the installed product operations. Linux + Docker Compose v2.30.

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

dotenv_value() {
    sed -n "s/^$1=//p" "$2"
}

reset_compose_environment() {
    unset APP_IMAGE APP_PORT ALLOWED_HOSTS PIXABAY_API_KEY SITE_LOGO APP_COMPOSE_PROJECT \
        APP_MANAGED_ENV_FILE APP_DEPLOY_MODE COMPOSE_PROFILES CELERY_CONCURRENCY \
        WEB_MEMORY_LIMIT WORKER_MEMORY_LIMIT BEAT_MEMORY_LIMIT SEEDKIT_MEMORY_LIMIT
}

host_lock() {
    exec 8>>"${SCAFFOLD_HOST_LOCK:-/run/lock/scaffold-deploy.lock}"
    flock -x -w "$1" 8 || fail "服务器正在启动产品或初始化数据，请稍后重试"
}

product_lock() {
    exec 9>>"$1"
    flock -x 9
}

seed_jobs_running() {
    jobs=$(docker ps --filter label=org.django-scaffold.seedkit-run "$@" --format '{{.ID}}') ||
        fail "无法查询数据初始化容器"
    [ -z "$jobs" ] || fail "服务器正在初始化数据，请稍后重试"
}
