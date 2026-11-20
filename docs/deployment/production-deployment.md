# 生产部署说明

## 一、配置入口

优先在中台配置全局变量和产品变量。同名变量由产品值覆盖全局值，合并后以同名 `workflow_dispatch` input 传入 `deploy.yml`。手动部署可在项目的 **Settings → Secrets and variables → Actions** 配置工作流支持的 GitHub Secrets 作为后备值。部署模式通过运行工作流时选择或由服务器沿用已发布的值。

## 二、流水线连接配置

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
| `APP_DEPLOY_MODE` | 由服务器解析 | 在中台为单个产品设置 `web`、`worker` 或 `scheduled` |

## 三、同一服务器部署多个应用

给每个应用配置固定且独立的 `DEPLOY_PATH`、已分配的 `APP_PORT` 及独立的 ACR 镜像仓库。例如目录 `/opt/reading` 和 `/opt/catalog` 可以分别映射端口 `8101` 和 `8102`。使用 Docker Compose v2.30 或更新版本，并确保 Linux 服务器有 `flock`、`sha256sum` 和 `python3`。

在宿主机预先创建共享锁 `/run/lock/scaffold-deploy.lock`，让所有用于发布和中台 SSH 的账户可写。使用非 root 账户时，将锁文件设为这些账户所在组可写，并通过系统临时文件配置在重启时重建。全部产品须使用同一个锁文件。发布和中台启停使用同一宿主机锁，一次性初始化容器通过标签占用初始化名额直到退出。

| `APP_DEPLOY_MODE` | 常驻服务 | 使用条件 |
| --- | --- | --- |
| `web` | Web | 同步交互，数据初始化走一次性容器 |
| `worker` | Web、Worker | 产品有请求投递的异步任务 |
| `scheduled` | Web、Worker、Beat | 产品启用了周期任务，同产品仅运行一个 Beat |

新部署留空时使用 `web`。已有部署但未记录模式时使用 `scheduled`，之后留空会沿用已发布的模式。新版工作流接收 `APP_DEPLOY_MODE`，升级前清理实际传给该仓库的旧 `COMPOSE_SERVICE` input。中台产品服务的 Web 状态探测字段可继续使用 `web`。降档前核对周期计划、正在执行和等待消费的任务。发布会移除当前项目中停用的 Worker 或 Beat，媒体卷随原项目保留。

在中台按下表配置生产运行变量。每个应用使用独立的 MySQL 数据库。Redis 可共用实例及逻辑库，Compose 为 Web、Worker 和 Beat 注入相同的应用级 Redis 键前缀。

| 变量 | 建议作用域 | 配置规则 |
| --- | --- | --- |
| `SECRET_KEY` | 产品变量（敏感） | 每个产品设置并保管自己的 Django 密钥 |
| `REDIS_URL` | 全局变量（敏感） | `worker` 与 `scheduled` 必填，`web` 可省略。同机 Redis 使用容器可达的宿主机地址，绑定和防火墙仅开放所需内网来源 |
| `MYSQL_HOST`、`MYSQL_PORT` | 全局变量 | 使用分项配置时，共用 RDS 的产品可共享主机和端口。端口省略时使用 `3306` |
| `MYSQL_DATABASE`、`MYSQL_USER`、`MYSQL_PASSWORD` | 产品变量 | 配置产品专属数据库及账号，密码标为敏感 |
| `DATABASE_URL` | 产品变量（敏感） | 可用完整 MySQL URL 替代 `MYSQL_*`，其中的凭据应按 URL 规则编码。配置时 Django 优先使用该 URL |

使用分项配置时，确保全局变量、产品变量和 GitHub Secrets 都没有给该产品提供 `DATABASE_URL`。运行变量使用单行值。中台敏感标记保护存储和中台展示，流水线会给凭据加日志掩码。能访问 GitHub Actions 触发数据的人员可能看见 dispatch inputs。若需避免把某个凭据放入触发数据，可只在 GitHub Secrets 中配置该键。

提供任一运行变量后，流水线要求同时提供 `SECRET_KEY` 和一套完整的 MySQL 配置。异步模式由服务器检查 Compose 合并后的 `REDIS_URL`。部署生成权限为 `600` 的 `DEPLOY_PATH/deploy/.env.runtime.managed`，常驻服务与一次性容器共同读取。各受管键覆盖已有 `deploy/.env.runtime` 的同名键。新项目及接管后的每次发布都要提供完整的受管配置。首次接管前，旧项目未传入运行变量时可继续使用已有的 `deploy/.env.runtime`。根目录 `.env.example` 提供配置样例，本地由 `make env` 生成 `.env`，线上由流水线生成独立的部署配置和受管运行配置。

流水线以服务器部署目录的实际路径生成稳定的 `APP_COMPOSE_PROJECT`，并记录到 `deploy/.env`。不同项目各自拥有容器、默认网络和媒体卷，同一项目修改端口仍会更新原来的容器和媒体卷。部署目录归属于首次部署该目录的仓库，部署其他应用时请使用不同目录。

在 Actions → Deploy → Run workflow 或中台发起部署。流水线按镜像 digest 更新已启用服务，并等待 Web 的 `/healthz/` 通过及已启用的 Worker、Beat 进入运行状态。Web 启动过程中执行迁移及静态资源收集，Worker 和 Beat 等到 Web 健康后启动。流水线失败时输出当前服务状态和近期日志。

容器内健康探针每 5 秒检查一次 Web。Gunicorn 省略内部探针成功返回 HTTP 200 的访问日志，保留异常响应及其他访问记录。

Web 默认在迁移前检查 Django 实际使用的 MySQL 主机和端口。`SKIP_DB_WAIT=1` 可跳过检查。

## 数据库地址排查

出现 `Temporary failure in name resolution` 时，在部署服务器用 `getent ahostsv4 RDS域名` 检查宿主机解析。宿主机解析正常时，可在应用目录复用下文的 `compose` 函数，从该应用的网络执行 `compose run --rm --no-deps --entrypoint getent web ahostsv4 RDS域名` 检查容器内的解析。

如果只有容器报 DNS 失败，检查 Docker 的 DNS 上游是否能解析该 RDS 地址。如果域名可解析但 TCP 连接失败，核对新服务器到 RDS 的网络路由、端口及 RDS 白名单。旧应用接管时应将原业务数据库的连接信息录入中台。

## 四、升级旧部署

旧编排使用 `deploy` 作为默认项目名。Docker 可能已经将多次部署的容器和媒体写入同一个项目。升级前停止该主机上的旧版部署任务，并使用 Docker 的 Compose 标签和端口确认当前容器归属。遇到混用的旧媒体卷时先备份，再根据各应用的数据库文件记录确认归属。

```bash
docker ps -a --filter label=com.docker.compose.project=deploy \
  --format '{{.Names}} {{.Ports}} {{.Label "com.docker.compose.project.working_dir"}}'
docker volume ls --filter label=com.docker.compose.project=deploy
```

1. 在各应用目录将现有的生产连接配置录入中台，确保它们指向各应用原来的数据库。对于当前占用旧项目的应用，备份其数据库和媒体卷并安排切换窗口。
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

中台「触发部署」继续调用 GitHub Actions 的 `workflow_dispatch`，`workflow_file` 填 `deploy.yml`。中台注入产品服务的 `deploy_path` 为 `DEPLOY_PATH`，从密钥文件注入 `SSH_KEY`，并从部署变量传入 `SSH_HOST`、`APP_PORT` 和可选的 `APP_DEPLOY_MODE`。每个应用使用自己固定的绝对部署路径及端口。

中台通过 SSH 执行启停、查询或数据初始化时，将该产品的 `deploy_path` 作为 `DEPLOY_PATH` 传给远端 Shell。下面的前置代码和表格中的一条操作命令放在同一次 SSH 执行中。

```bash
set -eu
cd "$DEPLOY_PATH"
PROJECT=$(sed -n 's/^APP_COMPOSE_PROJECT=//p' deploy/.env)
if [ -z "$PROJECT" ]; then
    echo "缺少 APP_COMPOSE_PROJECT，请先完成新版部署" >&2
    exit 1
fi
unset APP_IMAGE APP_PORT ALLOWED_HOSTS PIXABAY_API_KEY SITE_LOGO APP_MANAGED_ENV_FILE COMPOSE_PROFILES
compose() {
    APP_COMPOSE_PROJECT="$PROJECT" docker compose -p "$PROJECT" \
      --env-file deploy/.env -f deploy/docker-compose.yml "$@"
}
```

| 场景 | 命令 |
| --- | --- |
| 查看服务状态 | `compose ps -a` |
| 查看日志 | `compose logs --tail=100` |
| 按已发布配置启用 | `sh deploy/product-runtime.sh start 180` |
| 停用本应用 | `sh deploy/product-runtime.sh stop` |
| 异步初始化业务数据 | `sh deploy/product-runtime.sh seed-trigger` |
| 查询本次初始化进度 | `sh deploy/product-runtime.sh seed-status "$RUN_ID"` |
| 进入 Django Shell | `compose exec web python manage.py shell` |

异步初始化成功投递后，从命令 stdout 的 JSON 读取 `run_id`，将它作为 `RUN_ID` 传给后续查询，并在同一应用目录轮询。操作参数和返回状态见[种子数据指南](../project/seed-data-guide.md#本地与线上命令)。

执行命令的系统账号需有 Docker 权限、能读取部署配置，并已对私有 ACR 执行 `docker login`。发布文件固定上次流水线的镜像 digest，重新启用会使用对应版本。

## 六、2 核 2G 试点与回退

Web 默认使用 1 个 Gunicorn worker、2 个线程和 224 MiB 内存上限。Worker 使用 prefork 并发 1 和 256 MiB 上限。Beat 上限为 128 MiB，一次性初始化上限为 192 MiB。这些值是首轮压测起点。记录同机 Redis 的 RSS、队列及内存压力，确认队列使用期间没有因 Redis 内存策略而丢弃任务键。

1. 先发布兼容新版运行脚本的中台后端，再用原模式重发一个现有产品。随后挑选一个纯 Web 产品降档，验证中台启停、初始化和媒体访问。
2. 逐个启动 4 个纯 Web 产品和 1 个 Web/Worker 产品。连续 30 分钟给每个产品 2 个并发访客，覆盖首页及实际访问数据库的列表或详情。在压测中错开执行代表性异步任务、纯 Web 初始化和一次产品发布。单独启用 Beat 测试周期任务是否由单实例投递并消费。
3. 采集整机 CPU 和 `MemAvailable`、容器内存与重启次数、Redis RSS 与队列深度，以及各产品页面响应耗时。通过线为无 OOM、无异常重启、请求无 5xx、页面 p95 ≤ 1 秒、整机可用内存最低 ≥ 256 MiB。
4. 每次试点先记录发版前的镜像 digest、Git 提交和模式。应用失败时，以前一版 digest、对应发布文件和原模式回发单个产品，涉及数据库迁移时按产品的迁移兼容性处理。发布后的模板变更不覆盖其他产品。
