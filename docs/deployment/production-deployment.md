# 生产部署说明

## 一、环境变量（GitHub Secrets）在哪里配置

1. 打开项目 GitHub 页面 → **Settings** → 左侧 **Secrets and variables** → **Actions**；
2. 在 **Secrets** 页点 **New repository secret**，逐个添加下表中的 key/value；
3. 流水线中通过 `${{ secrets.XXX }}` 引用，改完即时生效，无需改 yml。

## 二、Secret key 与值说明

### 必填

| Key | 值说明 | 示例 |
| --- | --- | --- |
| `ACR_REGISTRY` | 阿里云镜像仓库地址 | `registry.cn-hangzhou.aliyuncs.com` |
| `ACR_NAMESPACE` | ACR 命名空间 | `my-team` |
| `ACR_USERNAME` | ACR 登录账号（阿里云账号全名） | `aliyun@xxx.onaliyun.com` |
| `ACR_PASSWORD` | ACR 访问凭证密码（在 ACR 控制台「访问凭证」设置） | `********` |
| `SSH_HOST` | 服务器公网 IP 或域名，只填地址，**不要带 `user@` 或端口** | `43.143.145.111` |
| `SSH_USER` | 服务器登录用户名 | `root` |
| `SSH_KEY` | SSH **私钥全文**（`-----BEGIN ... PRIVATE KEY-----` 开头），对应公钥需已写入服务器 `~/.ssh/authorized_keys` | 粘贴私钥内容 |
| `DEPLOY_PATH` | 服务器部署目录，流水线会把 compose 文件传到 `$DEPLOY_PATH/deploy/` | `/opt/django-scaffold` |
| `APP_HOST` | 浏览器访问的域名/IP，多个用英文逗号分隔，注入 Django `ALLOWED_HOSTS`（流水线会自动追加 `localhost,127.0.0.1`，不必手写） | `example.com` |

### 可选（留空走默认值）

| Key | 默认值 | 说明 |
| --- | --- | --- |
| `ACR_REPOSITORY` | `django-scaffold` | ACR 仓库名 |
| `SSH_PORT` | `22` | SSH 端口，仅数字 |
| `SSH_PASSPHRASE` | 空 | 私钥口令，私钥无口令就不要配 |
| `APP_PORT` | `8000` | 宿主机对外映射端口（服务器防火墙/安全组需放行） |

## 三、同一服务器部署多个应用

给每个应用配置固定且独立的 `DEPLOY_PATH`、已分配的 `APP_PORT` 及独立的 ACR 镜像仓库。例如目录 `/opt/reading` 和 `/opt/catalog` 可以分别映射端口 `8101` 和 `8102`。使用 Docker Compose v2.24 或更新版本，并确保 Linux 服务器有 `flock` 和 `sha256sum`。

在每个应用的 `DEPLOY_PATH/deploy/.env.runtime` 写入该应用专属的 Django `SECRET_KEY`、MySQL 连接配置（`DATABASE_URL` 或 `MYSQL_*`）和 `REDIS_URL`。把文件权限设为 `600`，并保证部署及执行中台启停的账号可读。每个应用使用独立的 MySQL 数据库，即使使用同一 RDS 实例也需分库。Celery Beat 的计划和任务结果存于应用数据库。Redis 可复用同一实例和逻辑库，Compose 会为 Web、Worker 和 Beat 注入一致的应用级键前缀。

流水线以服务器部署目录的实际路径生成稳定的 `APP_COMPOSE_PROJECT`，并记录到 `deploy/.env`。不同项目各自拥有容器、默认网络和媒体卷，同一项目修改端口仍会更新原来的容器和媒体卷。部署目录归属于首次部署该目录的仓库，部署其他应用时请使用不同目录。

在 Actions → Deploy → Run workflow 或中台发起部署。流水线按镜像 digest 更新 Web、Worker 和 Beat，并等待 Web 的 `/healthz/` 通过及 Worker、Beat 进入运行状态。Web 启动过程中执行迁移及静态资源收集，Worker 和 Beat 等到 Web 健康后启动。流水线失败时输出三个服务的状态和近期日志。

## 四、升级旧部署

旧编排使用 `deploy` 作为默认项目名。Docker 可能已经将多次部署的容器和媒体写入同一个项目。升级前停止该主机上的旧版部署任务，并使用 Docker 的 Compose 标签和端口确认当前容器归属。遇到混用的旧媒体卷时先备份，再根据各应用的数据库文件记录确认归属。

```bash
docker ps -a --filter label=com.docker.compose.project=deploy \
  --format '{{.Names}} {{.Ports}} {{.Label "com.docker.compose.project.working_dir"}}'
docker volume ls --filter label=com.docker.compose.project=deploy
```

1. 在各应用目录建立 `deploy/.env.runtime`，沿用该应用现有的生产连接配置。对于当前占用旧项目的应用，备份其数据库和媒体卷并安排切换窗口。
2. 核对旧容器确实属于待切换的应用后，从该应用的旧部署目录用旧 Compose 配置停止 Web 和 Beat，并让旧 Worker 处理完仍可归属该应用的队列任务。新部署启用独立 Redis 键前缀，原队列中的任务需在切换前处理或由业务方重新投递。多应用已共用旧队列时，应先核实任务归属，避免继续交叉消费。
3. 确认上述事项后，使用旧配置和经核对的项目名执行 `docker compose -p deploy --env-file deploy/.env -f deploy/docker-compose.yml down`，保留旧媒体卷。仍在运行的其他项目须使用各自标签确认归属。若旧项目名曾被显式设置，以实际标签为准。
4. 将本目录旧 `deploy/.env` 归档为 `deploy/.env.legacy`。流水线遇到旧格式 `deploy/.env` 会停止，以便在切换前完成检查。需要迁移媒体时，在第一次新部署前创建目标卷并从已核实的备份恢复，目标卷名称及标签见下方。
5. 对各应用分别触发新部署。部署第二个应用后，核对两个端口的 `/healthz/`、各自的 Worker/Beat、媒体和数据库。只重启或停用其中一个项目，再检查另一个项目仍可用。

在应用的 `DEPLOY_PATH` 下计算新卷名称并创建带有 Compose 标签的卷。恢复媒体时保留原文件的属主和权限。

```bash
HASH=$(printf '%s' "$(pwd -P)" | sha256sum)
PROJECT="scaffold-$(printf '%.20s' "$HASH")"
docker volume create \
  --label "com.docker.compose.project=$PROJECT" \
  --label com.docker.compose.volume=media_files \
  "${PROJECT}_media_files"
```

## 五、中台触发部署及远程命令

中台「触发部署」继续调用 GitHub Actions 的 `workflow_dispatch`，`workflow_file` 填 `deploy.yml`。中台将产品的 `deploy_host`、`deploy_path`、`host_port` 分别作为 `SSH_HOST`、`DEPLOY_PATH`、`APP_PORT` 传入。每个应用使用自己固定的绝对部署路径及端口。旧中台仍可传入 `COMPOSE_SERVICE`，流水线统一发布 Web、Worker 和 Beat。

中台通过 SSH 执行启停、查询或数据初始化时，将该产品的 `deploy_path` 作为 `DEPLOY_PATH` 传给远端 Shell。下面的前置代码和表格中的一条操作命令放在同一次 SSH 执行中。

```bash
set -eu
cd "$DEPLOY_PATH"
PROJECT=$(sed -n 's/^APP_COMPOSE_PROJECT=//p' deploy/.env)
if [ -z "$PROJECT" ]; then
    echo "缺少 APP_COMPOSE_PROJECT，请先完成新版部署" >&2
    exit 1
fi
unset APP_IMAGE APP_PORT ALLOWED_HOSTS PIXABAY_API_KEY SITE_LOGO
compose() {
    APP_COMPOSE_PROJECT="$PROJECT" docker compose -p "$PROJECT" \
      --env-file deploy/.env -f deploy/docker-compose.yml "$@"
}
```

| 场景 | 命令 |
| --- | --- |
| 查看服务状态 | `compose ps -a` |
| 查看日志 | `compose logs --tail=100 web worker beat` |
| 按已发布配置启用 | `compose up -d --wait --wait-timeout 180` |
| 停用本应用 | `compose down` |
| 异步初始化业务数据 | `compose exec -T web python manage.py seedkit_run --trigger platform` |
| 查询本次初始化进度 | `compose exec -T web python manage.py seedkit_status --run-id "$RUN_ID"` |
| 进入 Django Shell | `compose exec web python manage.py shell` |

异步初始化成功投递后，从命令 stdout 的 JSON 读取 `run_id`，将它作为 `RUN_ID` 传给后续查询，并在同一应用目录轮询。操作参数和返回状态见[种子数据指南](../project/seed-data-guide.md#本地与线上命令)。

执行命令的系统账号需有 Docker 权限、能读取部署配置，并已对私有 ACR 执行 `docker login`。发布文件固定上次流水线的镜像 digest，重新启用会使用对应版本。
