# 异步任务与定时任务 SOP（Celery + Redis）

> 面向团队零基础新手的标准作业流程。照本文操作即可在任意毕设业务系统中使用
> 「耗时任务异步化」与「定时任务」两项基座能力，无需理解底层原理。

## 一、架构总览

```
Web 进程（Django）                 Redis（云托管/共享开发实例）        Celery worker 进程
  任务 .delay() 提交  ─────注入队列────▶  broker 消息队列  ─────消费────▶  执行 apps/<模块>/tasks.py
       ▲                                                                    │
       │ 轮询任务状态                                    结果落库 ───────────┘
       │                                                       ▼
Celery beat 调度器  ──到点注入队列──▶ Redis            django_celery_results 表
（读 Admin 配置的周期任务，DatabaseScheduler）           （Admin「任务结果」可查）
```

关键组件：

| 组件 | 作用 | 位置 |
| --- | --- | --- |
| Redis | 消息队列（broker），任务在这里排队 | 云托管实例（生产）/ 共享开发实例（开发） |
| `config/celery.py` | Celery 应用装配，全局唯一 | 基座已就绪，业务开发一般不用改 |
| `apps/<模块>/tasks.py` | 任务定义 | 每个业务模块自己建 |
| django-celery-beat | 周期任务计划存数据库，Admin 动态管理 | Admin「定时任务」 |
| django-celery-results | 任务执行结果落库 | Admin「任务结果」 |

## 二、环境准备（每人一次性）

1. 向团队负责人索取**共享开发 Redis 地址**，写入项目根 `.env`：

   ```ini
   # 形如 redis://:密码@共享实例地址:6379/1（约定开发用 db1）
   REDIS_URL=redis://:xxx@xxx:6379/1
   ```

   未配置时默认回退 `redis://localhost:6379/1`（本机可用 Docker 起一个临时 Redis 调试：
   `docker run -d -p 6379:6379 redis:5-alpine`）。

2. 安装依赖：`make install`（Celery 已包含在基座依赖中，无需单独安装）。

## 三、本地开发启动（三个终端）

```bash
make run      # 终端 1：Web 服务（提交任务、查状态、Admin）
make worker   # 终端 2：worker，真正执行任务；改 tasks.py 后需重启此终端
make beat     # 终端 3：beat，只在需要验证定时任务时启动
```

> 注意：开发配置 DEBUG=False，无代码热重载，**修改 tasks.py 后必须重启 worker**（Ctrl+C 后重新
> `make worker`）；只改 services/views 则无需重启 worker。
>
> 本地 worker 默认使用 `-P solo` 单进程池：macOS（Python 3.12 默认 spawn）下 Celery 的默认
> prefork 池子进程会报 `ValueError: not enough values to unpack (expected 3, got 0)`，solo 可彻底避开；
> 毕设量级单进程完全够用。生产容器（Linux）仍用默认 prefork + 并发（见 `deploy/docker-compose.yml`）。

验证：worker 终端出现 `celery@... ready` 且显示的 broker 为 `.env` 的 `REDIS_URL`；beat 终端出现
scheduler 启动日志。业务模块接入任务后（见第四节），可在 Admin「任务结果」查看执行记录。

## 四、业务模块接入异步任务（SOP 四步）

以「商品报表导出」为例，假设业务 app 为 `apps/orders`：

1. **业务逻辑写 services**：`apps/orders/services.py` 中实现纯函数 `build_report(params) -> str`
   （可被 Web 进程和 worker 复用，禁止出现 Celery 相关内容）。
2. **建 tasks.py 薄壳**：`apps/orders/tasks.py`：

   ```python
   from config.celery import app
   from .services import build_report

   @app.task(name="apps.orders.tasks.build_report_task", bind=True)
   def build_report_task(self, params: dict) -> dict:
       self.update_state(state="PROGRESS", meta={"step": "生成中"})
       url = build_report(params)
       return {"url": url}
   ```

   任务全名必须写 `apps.<模块>.tasks.<函数名>`，Admin 配置定时任务时要填这个全名。
3. **视图只提交不执行**：在 `views.py`（或调用方）`build_report_task.delay(params)` 拿到
   `task_id`；若前端需实时展示进度，提供一个只读状态视图，用 HTMX 轮询（
   `hx-get` + `hx-trigger="every 1s"`），视图内部用 `app.AsyncResult(task_id)` 读状态。
4. **写测试**：全局 conftest 已开启 eager 模式，直接 `task.delay(...)` 同步断言结果，无需起 Redis/worker。

## 五、定时任务管理（Admin 操作）

后台左侧「定时任务」（周期任务均由业务模块在 Admin 手动添加，基座不再预置示例）：

1. 点「+ 添加」；
2. **任务名**填全名（如 `apps.orders.tasks.build_report_task`）；
3. 调度方式三选一：
   - 周期时间（Interval）：每 N 分钟/小时/天；
   - 定时时间（Crontab）：如每天 03:00（注意选择/创建时区为 Asia/Shanghai 的计划）;
   - 一次性（Clocked）：指定日期时间执行一次；
4. **位置参数 / 关键字参数**必须是合法 JSON（如 `["a", 1]`、`{"keep_hours": 24}`），留空即无参；
5. 保存后确认「启用」勾选；暂停某任务 = 取消勾选（不是删除）。

新配置**1 分钟内**被 beat 自动感知，无需重启。验证：到点后到「任务结果」查看执行记录。

## 六、查看任务执行记录

- 后台「任务结果」：状态、发起人参数、返回值、失败完整堆栈（traceback）、执行耗时；
- 失败排查顺序：结果详情看异常 → worker 终端日志（Loguru 统一输出）→ 确认任务全名/参数 JSON 是否正确。

## 七、生产部署

- 中间件为**阿里云托管 Redis**：`REDIS_URL` 填内网地址（db0），经镜像内 `.env` / CI Secret 注入；
- `deploy/docker-compose.yml` 已含 `worker` / `beat` 服务，与 `web` 共用镜像，`make docker-up`
  或直接 `docker compose -f deploy/docker-compose.yml up -d` 一并拉起；
- 数据库迁移只由 web 入口执行，worker/beat 启动顺序已声明 `depends_on: web`；
- 「任务结果」表会持续增长：建议业务稳定后新增一个清理任务（定期删除 N 天前的
  `TaskResult`），并在 Admin 配为每日周期任务，避免无限增长。

## 八、新手 FAQ

| 现象 | 原因与处理 |
| --- | --- |
| 状态一直 PENDING | worker 没启动（`make worker`），或任务全名拼错（worker 日志会提示未注册） |
| 启动报 Connection refused | `.env` 的 `REDIS_URL` 错误 / 共享实例密码过期 / 网络不通，用 `redis-cli -u "$REDIS_URL" ping` 验证 |
| worker 报 `not enough values to unpack (expected 3, got 0)` | macOS 下用了默认 prefork 池；本地请用 `make worker`（已内置 `-P solo`），手动启动时加 `-P solo` |
| 定时任务到点不执行 | beat 没启动；或该任务「启用」被取消；或 Crontab 计划时区不对 |
| 改了 tasks.py 不生效 | 开发环境无热重载，重启 worker 终端 |
| Web 能跑但任务全失败 | worker 连的 Redis db 号和 Web 不一致（都要用同一个 `REDIS_URL`） |
| 测试报连不上 Redis | 不会——全局 conftest 已强制 eager 模式，若失败请检查是否在 tasks.py 里写了连接逻辑 |

## 九、边界与约定

- 任务必须**幂等可重试**：worker 可能因超时/重启重复投递同一任务；
- 任务参数只传 ID/简单 dict，**不要传 queryset、文件对象、请求对象**（无法序列化）；
- 长任务控制在 30 分钟内并阶段性 `update_state`，更长的流程拆成多个任务串联；
- 基座约定不启用 Flower 等额外监控，观测入口统一为 Admin「任务结果」。
