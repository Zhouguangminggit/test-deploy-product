# seedkit 中台接入说明

> 面向中台（FastAPI）通过受控 SSH 触发业务系统数据初始化的接入文档，只描述流程步骤。
> 业务系统侧能力由 `apps/seedkit` 提供：管理命令 `seedkit_run` / `seedkit_status`、
> Celery 异步执行、运行记录与逐条日志落库（后台可查）。

## 一、总体流程

```
中台 ──SSH──▶ 业务系统容器 (web) ──执行──▶ manage.py seedkit_run
                                              │  创建 SeedRun(pending) 并投递 Celery
                                              ▼
                                         worker 异步执行填充
中台 ◀──stdout JSON(run_id)──────────────────┘
  │
  └──SSH 轮询──▶ manage.py seedkit_status --run-id <id> ──▶ stdout JSON(状态/统计/日志)
```

- 触发与查询都以 **stdout 单行 JSON** 为契约，过程日志走 stderr（loguru）与数据库，互不干扰；
- 触发命令投递任务后**立即返回**（不等执行完成），中台据 `run_id` 轮询进度。

## 二、前置条件

| 项 | 说明 |
| --- | --- |
| worker 容器在线 | 实际填充在 Celery worker 执行，`docker compose -f deploy/docker-compose.yml ps` 应见 `worker` 为 running |
| Redis 可用 | 作为 Celery broker；不可达时 `seedkit_run` 投递失败并以非零码返回 |
| 配置随镜像发布 | `seeds/seed_data.yml` 打包进镜像，路径由 `SEEDKIT_CONFIG` 指定 |
| 密钥已注入 | 需下载图片时 `PIXABAY_API_KEY` 必须非空（见第三节）；留空则跳过图片、仅填结构化数据 |

## 三、环境变量注入（PIXABAY_API_KEY）

1. 中台在**产品变量**中以 `PIXABAY_API_KEY` 为 key 配置密钥（与现有 `SSH_*`、`APP_PORT` 等约定一致）；
2. 触发部署时经 GitHub Actions `workflow_dispatch` 的同名 input 传入；
3. 流水线将其写入服务器 `deploy/.env`（并做日志掩码），compose 的 `web`/`worker` 服务自动读取注入；
4. 未提供 input 时回退仓库 `secrets.PIXABAY_API_KEY`。

> 密钥只用于 worker 侧调用 Pixabay 下载图片，不入库、不回显到中台日志。

## 四、触发初始化

SSH 进入部署目录后，在 `web` 容器内执行 `seedkit_run`（缺省异步投递 Celery）：

```bash
ssh <SSH_USER>@<SSH_HOST> "cd <DEPLOY_PATH> && \
  docker compose -f deploy/docker-compose.yml exec -T web \
  python manage.py seedkit_run"
```

- 可选参数：`--module <名>`（只初始化指定模块，可重复）、`--refresh`（先逆序清空再重填）；
- **stdout 输出**（示例）：

```json
{"run_id": 12, "task_id": "9f1c...", "status": "pending"}
```

- 中台解析该行 JSON 取 `run_id` 用于后续轮询；
- 退出码：`0` 投递成功；非 `0` 表示投递失败（如 Redis 不可达），此时 stdout 仍输出含
  `"status": "failed"` 与 `error` 的 JSON，便于中台判定失败原因。

## 五、轮询进度

```bash
ssh <SSH_USER>@<SSH_HOST> "cd <DEPLOY_PATH> && \
  docker compose -f deploy/docker-compose.yml exec -T web \
  python manage.py seedkit_status --run-id 12"
```

- `--run-id` 缺省取最近一次运行；`--tail N` 控制返回的日志条数（默认 50）；
- **stdout 输出**（示例）：

```json
{
  "run_id": 12, "status": "success", "trigger": "platform", "refresh": false,
  "modules": [], "celery_task_id": "9f1c...",
  "created": 42, "skipped": 0, "images": 10, "error": null,
  "started_at": "2024-05-01T10:00:00+08:00",
  "finished_at": "2024-05-01T10:00:08+08:00",
  "logs": [{"level": "info", "message": "[products] ...：新增 3 条", "at": "..."}]
}
```

- 建议轮询间隔 2~5s，直到 `status` 进入终态（`success` / `partial` / `failed`）。

### 状态机

| status | 含义 | 中台处理 |
| --- | --- | --- |
| `pending` | 已创建、待 worker 拉取 | 继续轮询 |
| `running` | 执行中 | 继续轮询 |
| `success` | 全部模块成功 | 结束，读取 `created/skipped/images` |
| `partial` | 部分模块失败（已回滚失败模块，成功模块保留） | 结束，读 `error` 提示失败模块 |
| `failed` | 配置校验失败或整体异常 | 结束，读 `error` 定位 |

## 六、日志与追溯

- **业务系统日志**：填充过程经 loguru 输出（`docker compose ... logs -f --tail=100 worker`）；
- **数据库留痕**：每次运行一条 `SeedRun`，逐条过程日志 `SeedRunLog`，均可在业务系统
  Django 后台「数据初始化」菜单只读查看（含状态、统计、错误、日志内联）；
- `seedkit_status` 返回的 `logs` 即上述落库日志的尾部若干条，中台可直接展示给运营。

## 七、命令速查

| 目的 | 命令（容器内） |
| --- | --- |
| 异步触发全部模块 | `python manage.py seedkit_run` |
| 触发指定模块 | `python manage.py seedkit_run --module products` |
| 强制重填 | `python manage.py seedkit_run --refresh` |
| 查询最近一次 | `python manage.py seedkit_status` |
| 查询指定运行 | `python manage.py seedkit_status --run-id 12 --tail 100` |
| 本地同步执行（调试） | `python manage.py seedkit_run --trigger local --sync` |

> YAML 配置写法与字段规则见 `docs/project/seed-data-guide.md` 与 `seeds/README.md`。
