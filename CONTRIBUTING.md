# 贡献指南

## 项目结构

```text
├── docker-compose.yml      # Tinode 与 MySQL 本地栈
├── branding/               # Web 界面品牌覆盖层
├── npc/                    # Python AI NPC 工作进程
├── client/                 # PySide6 Qt 客户端
├── desktop-tauri/          # Tauri 桌面壳
└── .github/workflows/      # 构建与发布配置
```

## 开发流程

1. 在项目根目录运行 `docker compose up -d`。
2. 运行 `cd npc && ./start.sh` 启动 NPC。
3. 打开 `http://localhost:6060/`，或启动一个桌面客户端。

首次开发 Tauri 桌面端时运行：

```bash
cd desktop-tauri
npm ci
npm run check
npm run build
```

`npm run dev`、`npm run check` 和 `npm run build` 都会自动准备 `dist/index.html`。不要在外部脚本中复制这一步。

## 代码约定

- Python：沿用现有类型标注和标准库 `unittest`；异步、配置与协议边界必须保持类型清晰。
- Node.js：优先使用 Node.js 标准库，测试使用内置 `node:test`，不为简单构建任务新增依赖。
- Rust：提交前执行 `cargo fmt --check`、`cargo test` 和 `cargo check`。
- Shell：脚本使用 `set -euo pipefail`，不得写死个人目录。
- 文本：文档、注释、日志、错误提示和测试名称使用简体中文；协议字段与代码标识符保持原有英文命名。
- 品牌资源：修改 `branding/static/` 后运行 `branding/apply-brand.py` 并重启 Tinode。
- 生成文件：不提交 `desktop-tauri/src-tauri/gen/schemas/` 和构建产物。

## 提交改动

- 每次提交只解决一个可验证的问题。
- 启动流程或依赖变化时同步更新 README 和锁文件。
- Pull Request 中写明本地验证命令与结果，不把远程流水线当作唯一验收手段。
- 改动 Docker 配置后至少通过 Compose 官方 Schema 校验；本机有 Docker 时再执行 `docker compose config`。

## NPC 角色

角色的唯一事实来源是 `npc/vibechat_npc/roster.py`。需要导出 JSON 时运行：

```bash
cd npc
python3 gen_personas.py
```

随后重启 NPC 工作进程。
