# AshenSupport

有依据的诊断，有边界的执行。Vue 3 + Python 的开源项目技术支持工作台。

流程：问题 → 文档检索 → 受限诊断 → 带引用建议 → 人工审核 → 项目内工单。

前端采用新粗野主义：纸白、粗黑边框、方角硬阴影、亮黄/珊瑚红/薄荷青，覆盖全部页面与组件。

默认使用 **fake provider**，无需模型 Key；界面明确标注模拟数据。该模式用于验证工程流程，不能证明真实 AI 回答质量。

## 文档

- [产品需求](PRD.md)
- [详细开发计划](DEVELOPMENT_PLAN.md)
- [实际验证状态与限制](docs/VERIFICATION.md)
- [架构与取舍](docs/architecture.md)
- [运行与故障处理](docs/runbook.md)
- [演示脚本](docs/demo.md)

## Docker 启动

要求 Docker Engine/Compose。只绑定本机 8180，不自动发布公网。

```powershell
Copy-Item .env.example .env
# 编辑 .env 的 POSTGRES_PASSWORD；推荐随机十六进制，避免 URL 特殊字符。
docker compose up -d --build
```

打开 <http://localhost:8180>。`ASHEN_ORIGIN` 必须和浏览器实际来源完全一致（包括 localhost 与 127.0.0.1 的区别）。默认迁移后导入两个项目公开 README 快照；worker 随后建立索引。首次等索引完成后再演示引用。

```powershell
docker compose logs --tail 50 worker
docker compose exec api python -m app.cli admin --username admin
```

管理员密码交互输入，不提供默认密码。关闭使用 `docker compose down`，不加 `-v`，以保留数据库。

## 本地开发

后端要求 Python 3.12 + uv。前端要求 Node.js 22.12+、pnpm 12.5.1。

```powershell
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.cli seed
uv run uvicorn app.main:app --reload
```

另开终端，在 backend 运行 `uv run python -m app.worker`。第三个终端：

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

默认本地使用 SQLite，仅用于便捷开发和单元测试；并发语义必须在 PostgreSQL 验证。默认前端来源 `http://localhost:5173`。根目录 `.env` 只用于 Compose，本地 backend 可放自己的 `.env` 或使用环境变量。

## 质量检查

后端：

```powershell
uv run ruff check .
uv run mypy app
uv run pytest -q
```

前端：

```powershell
pnpm lint
pnpm typecheck
pnpm test:unit
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
```

浏览器测试默认连接已启动的 <http://localhost:8180>；可通过 `ASHEN_E2E_URL` 覆盖。

真实 PostgreSQL 测试使用**独立可丢弃测试库**，测试会清空其表，绝对不要指向业务库：

```powershell
docker compose -f compose.test.yaml up -d --wait
cd backend
$env:ASHEN_TEST_DATABASE_URL='postgresql+psycopg://ashen:ashen-test-only@127.0.0.1:55439/ashen_test'
uv run pytest -q
```

## 在线模型

在服务端配置以下环境变量，重建 API 与 worker：

| 配置 | 说明 |
| --- | --- |
| ASHEN_PROVIDER | online |
| ASHEN_CHAT_URL | 完整聊天请求 URL，例如供应商文档中的 `/v1/chat/completions` |
| ASHEN_CHAT_KEY / ASHEN_CHAT_MODEL | 凭证与模型 ID |
| ASHEN_EMBEDDING_URL | 完整 embeddings URL |
| ASHEN_EMBEDDING_KEY / ASHEN_EMBEDDING_MODEL | 凭证与模型 ID |
| ASHEN_EMBEDDING_DIMENSIONS | 服务实际返回维度 |
| ASHEN_EMBEDDING_BATCH_SIZE | 单请求文本数，默认 8；每批仍严格校验返回 index 与维度 |
| ASHEN_RETRIEVAL_MODE | vector / hybrid / rerank |
| ASHEN_RERANK_URL / KEY / MODEL | 可选重排完整 URL、凭证和模型 |

适配器使用 chat-completions/embeddings JSON 形状；重排约定 `results[].index`。供应商的具体模型、JSON 模式和额度兼容性需要真实验证，不保证任意 endpoint 通用。切换 embedding 后须重新索引。

2026-10-02 实测：当前配置的 `Qwen/Qwen3-VL-Embedding-8B` 返回 4096 维，32 条输入时返回 index 每 8 条重置。适配器通过拆为最多 8 条的小批次兼容，继续拒绝重复 index，不能直接按返回顺序忽略索引。聊天 URL 必须包含请求路径，不能仅填写主机基础地址。

`ASHEN_INPUT_PRICE_PER_MILLION`、`ASHEN_OUTPUT_PRICE_PER_MILLION` 可设置生成模型每百万 token 单价，两者使用同一币种；未配置时费用未知。不同模型价格不可混用。embedding/rerank 费用当前保持未知。

## 评估

在 backend：

```powershell
uv run python -m app.evals run --suite smoke --provider fake
uv run python -m app.evals run --suite dev --provider fake --mode hybrid
# 只有明确配置在线服务后才执行：
uv run python -m app.evals run --suite test --provider online
```

`evals/datasets/cases.json` 有 80 条**待人工校对**的案例草稿，50/30 分层划分。生成器只用于初始准备，后续人工标注不要再次运行覆盖。报告将机器契约检查与人工效果指标分开；参考答案、gold chunks 和人工评分补全前，准确率与 Recall@5 保持未知。

## 素材与安全边界

`fixtures/docs/manifest.json` 记录两个公开 README 的仓库、commit、工作区是否修改以及实际文件哈希。启动不依赖相邻仓库。`scripts/prepare_fixtures.py` 是显式更新工具，只读取白名单 README，不读取 .env、私有材料或密钥。原项目许可不因快照发生改变。

真实诊断目标以 `ASHEN_HEALTH_TARGETS` 的 JSON 映射配置，如 `{"courier":"https://example.com/healthz"}`。访客不能调用。只支持公开 HTTPS，固定连接地址、TLS 校验、禁止重定向和私网。

本项目不执行 Shell/SSH、不自动修复、不自动写 GitHub，不把模型输出当权限依据。当前仅用安全的文本展示结果和引用。

## 许可

本仓库原创代码使用 [MIT License](LICENSE)，版权所有 © 2026 Elari39。引用的项目文档和第三方素材仍遵循其原有许可；来源见 `fixtures/docs/manifest.json`。
