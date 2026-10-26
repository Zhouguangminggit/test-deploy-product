# django-scaffold

## 项目定位

django-scaffold 是团队的**产品基座脚手架**：基于 Django 搭建好工程化底座（用户认证、文件管理、操作日志、消息通知、异步任务等通用能力已内置），团队成员按内部 SOP 流程在此基础上快速搭建各种毕设主题的业务产品项目，零基础新手也能照文档直接上手。

---

## 本地启动（按顺序做完即可）

### 第 1 步：安装 Python 3.12

- 下载地址：<https://www.python.org/downloads/release/python-3127/>（页面底部 Files 区，Windows 选 `Windows installer (64-bit)`，Mac 选 `macOS 64-bit universal2 installer`）
- **Windows**：安装时务必勾选 **"Add Python to PATH"**，再点 Install Now
- **Mac**：双击 pkg 一路继续即可

验证：打开终端（Windows 按 `Win+R` 输入 `cmd` 回车；Mac 在启动台搜索"终端"），输入 `python3 --version`，显示 `Python 3.12.x` 即成功。

### 第 2 步：配置环境变量（只有第 1 步验证失败才需要做）

- **Windows**：设置 → 搜索"编辑系统环境变量" → 环境变量 → 在"系统变量"里找到 `Path` → 编辑 → 新建，填入 Python 安装目录（一般为 `C:\Users\你的用户名\AppData\Local\Programs\Python\Python312\` 及其下的 `Scripts\` 目录）→ 确定后**重新打开**终端验证
- **Mac**：终端输入 `echo $SHELL`，若是 zsh 则执行 `echo 'export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc`，再验证

参考教程：<https://www.jb51.net/python/3134481xz.htm>

### 第 3 步：安装 uv（Python 包管理器）

- 下载地址：<https://docs.astral.sh/uv/getting-started/installation/>
- **Windows**：在终端执行 `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- **Mac**：在终端执行 `curl -LsSf https://astral.sh/uv/install.sh | sh`
- 执行 `uv --version` 有版本号输出即成功

### 第 4 步：安装 Node.js 22（前端样式构建用）

- 下载地址：<https://nodejs.org/en/download>，选 **Node.js v22（LTS）**，Windows 下载 `.msi` 一路下一步，Mac 下载 `.pkg` 一路继续（自带 npm，无需单独装）
- 执行 `node -v` 显示 `v22.x` 即成功

### 第 5 步：安装 Git 和 make

- **Git**（下载代码用）：下载地址 <https://git-scm.com/download/>，一路默认安装
- **make**（启动命令用）：
  - **Mac**：系统自带，无需安装（若提示安装 Command Line Tools，终端执行 `xcode-select --install` 按提示来）
  - **Windows**：安装 [MinGW-w64](https://github.com/niXman/mingw-builds-binaries/releases)（选 `x86_64-...-posix-sjlj-...zip`，解压后把其中 `bin` 目录加入 Path，方法同第 2 步）；执行 `make --version` 有输出即成功

### 第 6 步：获取项目并启动

打开终端，进入项目所在目录后**按顺序**执行：

```bash
make env        # 生成配置文件 .env（只需一次）
make install    # 安装依赖（只需一次，耗时几分钟）
make migrate    # 初始化数据库（只需一次）
make init-data  # 写入基础数据，含管理员账号（只需一次）
make css        # 构建前端样式（只需一次）
make run        # 启动服务
```

浏览器访问 <http://127.0.0.1:8000> 即可看到系统；后台管理入口为 <http://127.0.0.1:8000/admin>（默认账号 `admin` / `admin123456`，以 `make init-data` 的输出为准）。

> 以后每天开发只需执行 `make run` 一条命令。
> 全部可用命令可在终端执行 `make help` 查看。

---

## 遇到问题先查这里

| 现象 | 处理 |
| --- | --- |
| `python3` / `uv` / `node` / `make` 提示"不是内部或外部命令 / command not found" | 环境变量没配好，回到对应步骤的第 2 步或检查安装是否完成，**并重新打开终端** |
| `make` 报 `No rule to make target` | 确认终端当前目录在项目根目录（有 Makefile 的那个文件夹） |
| Windows 装 make 后仍找不到 | 确认加入 Path 的是 MinGW 的 `bin` 目录且已重开终端 |
| 页面样式错乱 | 执行 `make css` 后再 `make run` |
| 端口 8000 被占用 | 先用 `make run` 的窗口 Ctrl+C 关掉旧服务，或重启电脑后重试 |

异步任务、部署等进阶内容见 `docs/` 目录文档。
