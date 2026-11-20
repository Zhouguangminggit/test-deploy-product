# 产品部署模式配置

脚手架按产品启动 Web、Worker 和 Beat。纯 Web 产品在中台触发数据初始化时临时运行一个 `seedkit` 容器，完成后退出。中台仍可查看初始化进度。启用 Worker 的产品继续使用 Celery 初始化。

## 中台部署变量

唯一新增的变量是产品级 `APP_DEPLOY_MODE`，按产品需要填写：

| 值 | 适用场景 | 常驻服务 |
| --- | --- | --- |
| `web` | 页面展示和同步操作 | Web |
| `worker` | 有 Celery 异步任务 | Web、Worker |
| `scheduled` | 有启用的周期任务 | Web、Worker、Beat |

- 首次部署留空默认 `web`。已部署产品留空沿用已发布的模式。旧版部署首次升级且留空时使用 `scheduled`。
- `REDIS_URL` 是已有变量，`worker` 和 `scheduled` 必填，`web` 可省略。例如 `redis://:PASSWORD@192.168.1.10:6379/0`，请替换为产品容器可访问的 Redis 地址和实际凭据。
- 升级新版流水线时，清理发给该产品的旧部署变量 `COMPOSE_SERVICE`。中台用于状态探测的「Compose 服务名」仍可填 `web`。
