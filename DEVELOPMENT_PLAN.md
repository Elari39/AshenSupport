# AshenSupport 可执行开发计划

版本：v1.0 · 2026-10-02。对应 `PRD.md`。阶段是建议工程排期，不代表已经运行了 25 天。当前交付状态与命令结果见 `docs/VERIFICATION.md`。

## 1. 组织与依赖

6 周约 25 个有效开发日。4 周时减少视觉润色与可选重排，不减少授权、审批、并发和恢复测试。

依赖链：基础 → fake 完整闭环 → 知识库与在线适配 → 安全与可靠性 → 评估 → 部署与求职材料。

后端入口 `app/main.py`，数据库模型 `app/db.py`，工作流 `app/worker.py`；知识库、检索、模型、工具、安全、CLI 独立模块。前端分 api、stores、views；evaluation 在 evals，夹具在 fixtures，部署在 Compose/Dockerfile，运营材料在 docs。

首期按能力模块平铺 Python 文件，避免为每个小模块建立无内容的目录；复杂度增加后再拆包。

## 2. 阶段一：基础工程（第 1–3 日）

- 初始化 Python 3.12/uv 和 Vue3/TS/Vite，提交锁文件与版本声明。
- 配置 Ruff、mypy、pytest、ESLint、vue-tsc。
- 建立 SQLAlchemy、Alembic 初始迁移；禁止启动时偷偷修改表结构。
- 实现环境配置、统一错误、request ID 与日志脱敏。
- 实现匿名会话、CLI 管理员、Argon2id、登录轮换、CSRF/Origin。
- 前端路由、导航、API client、身份 store。
- 定义 fake/online provider 边界，初始 Compose。

验收：全新库迁移；访客/管理员入口；未授权访问拦截；无 API Key 可运行 fake 测试。

## 3. 阶段二：完整闭环（第 4–7 日）

- 定义任务状态、执行批次、消息、事件、步骤持久表。
- 实现 PostgreSQL 行锁领取、租约、心跳、旧 owner fencing。
- 用 fake provider 和固定模拟工具跑完整流程。
- 实现 SSE 事件保存、重连补发与客户端去重刷新。
- 工作台和任务列表支持补问、取消、失败重试。
- 工单草稿编辑增版、审批记录、事务创建、唯一约束与列表详情。

验收：刷新可恢复；同意重复提交同工单；访客隔离；旧 worker 无法覆盖取消/新租约；重启可恢复。

## 4. 阶段三：知识库与模型（第 8–12 日）

- 仅导入可公开的项目文档，记录来源仓库、commit、文件与哈希。
- 实现 Markdown/TXT 限制、哈希去重、版本与后台索引。
- 标题/段落分块、长段窗口、行号定位、向量存储。
- 索引完成原子激活；失败保留旧版本，引用快照独立保留。
- 向量检索基线与模型配置签名检查。
- 在线聊天/embedding 配置明确 endpoint、model、key；不宣称所有供应商通用。
- Pydantic 结果校验、一次格式修复、引用 ID 校验。
- 知识库管理页与来源详情。

验收：重复导入不重复计费；版本更新/停用行为正确；错误模型输出不能直接显示；在线模型验收需要实际凭证。

## 5. 阶段四：可靠性与边界（第 13–16 日）

- 固定目标 HTTPS 诊断，连接地址校验、TLS 校验、禁重定向、限制响应。
- 工具身份/模式授权、最多 3 次调用。
- 模型调用 45 秒、批次 180 秒、生成预算 4；有限重试并计费用量。
- Session/IP/global 原子额度；排队也占并发名额。
- usage 不完整时显示未知；用量页按 UTC 汇总。
- 取消后禁止写入；过期租约恢复与重复费用说明。
- 7 天访客数据清理；密码/API Key 不进入日志。

验收：访客真实工具拦截、私网和重定向拦截、畸形输出/超时/429、并发额度、并发批准与拒绝。

## 6. 阶段五：评估（第 17–20 日）

- 创建 80 条待校对案例及参考资料，分层 dev=50/test=30。
- 人工校对并冻结后才允许作为正式效果评估集。
- BM25 分词与缓存、RRF、可选重排适配。
- 三组实验保存模型、语料、参数、每条结果、耗时和费用可用性。
- 开发集选参数，测试集只做最终评价；保留基线避免选择性报告。
- 输出 JSON/Markdown，未执行项目明确标注。

验收：CLI 可复现；fake 测试无需密钥；在线执行显式选择；不可把 fake 成功率当 AI 准确率；人工指标未标注前保持未知。

## 7. 阶段六：交付（第 21–25 日）

- Compose 非 root API/worker/web，独立迁移，数据库持久卷。
- Nginx 同源代理、SSE 无缓冲，生产 Secure Cookie。
- 备份到文件并恢复到独立临时数据库验证。
- Playwright 三类演示，桌面/390px、刷新、断连、键盘、空/错误态。
- README 启动命令、架构、故障处理、诊断目标与模型配置。
- CI fake 测试、PostgreSQL 并发测试、浏览器测试、镜像构建。
- 准备 3–5 分钟讲解脚本和可复现浏览器证据；录屏如未制作应标记待完成。

验收：新环境可启动；引用可追溯；真实模型和真实目标分别验证；测试与报告真实；简历数字仅采用已验证数据。

## 8. 测试矩阵

| 类别 | 必测 |
| --- | --- |
| 权限 | 隔离、管理员、过期、CSRF、Origin |
| 索引 | 去重、失败保持旧版、停用、维度、长段行号 |
| 检索 | 中文、错误码、空语料、项目隔离、缓存版本 |
| 模型 | 429、超时、非法 JSON、未知引用、缺 usage |
| 工具 | 非授权、目标绕过、私网、重定向、超大响应 |
| 工作流 | 补问/工具上限、取消、旧租约、重启恢复 |
| 审批 | 重复、并发、拒绝、草稿过期、取消后审批 |
| SSE | 重放、终态、跨会话、游标 |
| 浏览器 | 三场景、引用、刷新、移动端 |
| 部署 | 全新迁移、Compose、备份恢复 |

## 9. 命令契约

后端（backend）：

```sh
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.cli seed
uv run uvicorn app.main:app --reload
uv run python -m app.worker
uv run pytest
uv run ruff check .
uv run mypy app
```

前端（frontend）：

```sh
pnpm install --frozen-lockfile
pnpm dev
pnpm lint
pnpm typecheck
pnpm test:unit
pnpm build
pnpm test:e2e
```

根目录 `docker compose up --build`；先复制 `.env.example` 为 `.env` 并填数据库密码。管理员 `docker compose exec api python -m app.cli admin`。

评估（backend）：

```sh
uv run python -m app.evals run --suite smoke --provider fake
uv run python -m app.evals run --suite test --provider online
```

CI：后端静态/单元 → PG 集成 → 前端静态/单元/构建 → fake 浏览器 → 镜像验证。在线评估仅手动触发。

## 10. 发布清单

- [ ] 文档与实现一致，已知限制显式记录。
- [ ] 全新克隆能够按 README 启动。
- [ ] 三类沙盒流程与工单闭环通过。
- [ ] PostgreSQL 并发与恢复测试通过。
- [ ] 两项目素材可追溯。
- [ ] 80 条案例人工校对并冻结。
- [ ] 在线聊天、embedding、可选 rerank 验证。
- [ ] 至少一个真实健康目标验证。
- [ ] 备份恢复、CI、浏览器验收通过。
- [ ] 3–5 分钟演示与失败分析完成。

这些是发布门槛，不能因代码文件存在就勾选。实际已完成项单独记录在验证报告中，避免静态计划与运行结果混淆。
