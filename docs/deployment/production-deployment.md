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

> 应用自身的运行配置（数据库、Redis、SECRET_KEY 等）**不通过 Secrets 配置**：构建镜像时
> `.env.example` 会被复制为镜像内 `.env`，其中 MYSQL_*、REDIS_URL 等值按项目实际情况修改
> `.env.example` 后随代码入库即可（团队当前约定）；只有与服务器相关的 `ALLOWED_HOSTS`、
> `APP_PORT` 由流水线用上述 Secrets 动态注入。

## 三、触发部署

- **自动**：`git push` 到 `main` 分支即触发；
- **手动**：Actions 页面 → Deploy 工作流 → **Run workflow**。

同一时间只跑一条部署（concurrency 已锁定），上一次没结束新提交会排队而非打断。

## 四、部署后服务器运维命令

流水线每次部署会在服务器生成 `deploy/.env`（含 `APP_IMAGE` / `APP_PORT` / `ALLOWED_HOSTS`），
Docker Compose 会自动读取 compose 文件同目录的 `.env`，因此**手动或中台系统执行命令前
不需要 export 任何变量**。中台系统的「启用/停用」即直接执行下表中的 up/down 命令。

先 SSH 登录服务器并进入部署目录：

```bash
ssh root@服务器IP
cd /opt/django-scaffold          # 即 DEPLOY_PATH
COMPOSE="docker compose -f deploy/docker-compose.yml"
```

> 前提：该用户需执行过 `docker login registry.cn-hangzhou.aliyuncs.com`（流水线部署时
> 已用同一用户登录过，凭证持久化在 `~/.docker/config.json`）。若中台用另一个系统用户
> 执行命令，需先用该用户再登录一次，否则拉取私有镜像会报 `pull access denied`。

| 场景 | 命令 |
| --- | --- |
| 查看三个服务状态（web/worker/beat） | `$COMPOSE ps` |
| 看实时日志（排错第一步） | `$COMPOSE logs -f --tail=100 web` |
| worker 日志 | `$COMPOSE logs -f --tail=100 worker` |
| 重启全部服务 | `$COMPOSE up -d --remove-orphans` |
| 只重启 web | `$COMPOSE restart web` |
| 手动拉新镜像并重启（中台「启用」等价于此） | `$COMPOSE pull && $COMPOSE up -d` |
| 直接启动（镜像已在本机，中台「启用」） | `$COMPOSE up -d` |
| 停止全部（中台「停用」） | `$COMPOSE down` |
| 进入容器内执行命令（如 Django shell） | `docker compose -f deploy/docker-compose.yml exec web python manage.py shell` |
| 磁盘/镜像占用清理 | `docker image prune -f` |

健康检查逻辑：流水线部署后轮询容器 `healthz` 接口最多约 2.5 分钟，`healthy` 即部署成功；
失败会自动输出 `web` 容器最近 100 行日志到 Actions 页面，排错先看那里。

## 五、新手 FAQ

| 现象 | 原因与处理 |
| --- | --- |
| `docker compose up -d` 报 `pull access denied for registry.cn-hangzhou.aliyuncs.com/your-namespace/...`，worker/beat 报 `context canceled` | 服务器 `deploy/.env` 缺失或内容不对，compose 回退到了占位镜像地址（`your-namespace` 不存在）。确认跑过一次流水线部署使其生成 `.env`，或手动写入真实 `APP_IMAGE`；`context canceled` 只是拉取失败后的连带表现。若 `.env` 正常但仍 denied，则是当前用户没登录过 ACR，`docker login` 一次即可 |
| 流水线报 `SSH_USER 为空或含非法字符` | Secrets 值里混了空格/换行或写成了 `root@host`，只填用户名 |
| `SSH 连接失败` | 公钥没加到服务器 `authorized_keys`；报错信息里会打印私钥对应公钥指纹，与服务器上的比对 |
| 构建推送 ACR 失败 `denied` | `ACR_USERNAME/ACR_PASSWORD` 错误或凭证过期，去 ACR 控制台重设访问凭证 |
| 部署成功但浏览器 400/打不开 | `APP_HOST` 没配或配错；确认安全组已放行 `APP_PORT` |
| 容器一直 unhealthy | `$COMPOSE logs web` 看报错；常见为镜像内 `.env` 的数据库/Redis 连不上 |
