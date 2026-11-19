# 文档目录说明

> 面向客户的文档与论文材料。各项目基于脚手架创建时，按本目录结构填充内容；
> 目录与文件命名为团队约定，请勿随意改动结构。

```
docs/
├── README.md                 # 本文件：文档目录说明
├── project/                  # 项目说明文档
│   ├── introduction.md       # 项目简介
│   ├── functional-description.md   # 功能说明（基础、核心、创新功能）
│   ├── technology-stack.md   # 技术栈说明
│   ├── catalog-architecture.md     # 目录架构说明
│   ├── seed-data-guide.md   # 种子数据填充指南（seedkit 统一 YAML 方案）
│   └── seedkit-platform-integration.md  # seedkit 中台接入说明（SSH 触发 / 轮询）
├── deployment/               # 部署文档
│   ├── local-deployment.md   # 本地部署说明
│   └── production-deployment.md    # 生产部署说明
├── thesis/                   # 毕业论文材料（按标准六章结构）
│   ├── README.md             # 论文材料说明
│   ├── abstract.md           # 摘要
│   ├── chapter-01-introduction.md          # 第一章：绪论
│   ├── chapter-02-related-technology.md    # 第二章：相关技术介绍
│   ├── chapter-03-system-analysis.md       # 第三章：需求分析
│   ├── chapter-04-system-design.md         # 第四章：系统设计
│   ├── chapter-05-system-implementation.md # 第五章：系统实现
│   ├── chapter-06-system-testing.md        # 第六章：系统测试
│   ├── conclusion.md         # 总结
│   ├── references.md         # 参考文献
│   └── acknowledgements.md   # 致谢
├── sop/                      # 团队内部 SOP（基座能力操作规范）
│   ├── celery-async-tasks.md # 异步任务与定时任务 SOP（Celery + Redis）
│   └── product-deployment-modes.md # 产品部署模式与中台配置
└── assets/                   # 文档与论文素材
    ├── architecture/         # 系统架构图
    ├── database/             # 数据库图
    └── screenshots/          # 系统截图
```

## 使用说明

- `project/`、`deployment/`：交付客户时必填，按项目实际业务内容撰写；
- `thesis/`：按学校模板裁剪章节，素材（截图、架构图、ER 图）统一放 `assets/`，通过相对路径引用；
- `sop/`：基座能力配套的操作规范，随基座版本维护，业务项目一般只读；
- `assets/` 子目录通过 `.gitkeep` 占位，放入文件后可删除对应 `.gitkeep`。
