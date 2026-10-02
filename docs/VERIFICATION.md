# 验证记录

日期：2026-10-02。以下运行结果来自本地 AshenSupport，不代表公网部署或 GitHub Actions 验收结果。

**后续更新：已接入并测试真实聊天与 embedding，当前服务为 online。完整结果、首轮失败与复测记录见 [真实模型测试](ONLINE_MODEL_TEST.md)。**

## 已验证

- PRD 与开发计划已保存；Vue 3 前端、Python API/worker、PostgreSQL/pgvector 和 Nginx 已构建并运行。
- 本地入口：http://localhost:8180。8080 已被其他项目占用，未停止其他服务。
- PostgreSQL 集成测试 **28 项通过**，覆盖访客隔离、CSRF/Origin、并发审批、并发创建任务、取消 fencing、租约恢复、引用校验、索引更新失败保留旧版、模型重试与额度、管理员文档校验、冻结迁移及人工评分边界。
- Ruff、mypy、ESLint、vue-tsc、Vitest（2 项）与前端生产构建通过。
- 浏览器三条完整流程通过：RAG→引用→审批→工单；移动端缓存场景；证据不足→三轮补问→明确结束。
- 新粗野主义覆盖工作台、任务、工单、知识库、登录、用量及下拉/抽屉/提示。六页在 390/768/1440px 无横向溢出，未出现 pageerror；截图和几何测量保存在 `output/screenshots/`。
- 短链服务真实健康探针：`https://shorten.miku831.fun/healthz` 返回 HTTP 200，白名单字段 status=ok、redis=ok。本机 `.env` 配置 courier 目标；仅管理员可调用。
- 两个公开 README 快照已建立索引，来源 commit/哈希在 `fixtures/docs/manifest.json`。
- `pg_dump -Fc` 已恢复到独立演练数据库，projects 计数为 2。备份位于被 Git 忽略的 `output/backup/`。
- 三分钟无旁白演示视频位于 `output/demo/AshenSupport-walkthrough.mp4`，展示实际浏览器交互与说明字幕；不是在线模型效果证据。

## 评估结果的口径

已执行 fake provider 的 smoke、dev/vector、dev/hybrid 报告，见 `evals/reports/`。这些只证明运行器和输出契约可执行，不能解释成语义准确率。

80 条案例为草稿，50 dev / 30 test，尚未人工校对参考答案。人工复核模板与评分器已经实现：`python -m app.score`，校验报告哈希，计算有标注样本的 Recall@5/正确率/引用支持率，不填充未知指标。

## 尚未完成的外部验收

- 在线聊天与 embedding 已完成小批量真实验收；重排未配置。首轮出现两例 JSON 输出解析失败，定向复测通过，稳定性与真实回答质量仍未完成大样本验收，准确费用未知。
- 数据集人工标注和固定测试集正式冻结仍需完成；当前不能发布准确率提升数字。
- GitHub Actions 工作流已配置，本地运行了对应核心检查，但没有远程仓库运行结果。
- HTTPS 公网部署与公网代理链验证未执行。

## 已知实现边界

- 小语料使用精确向量排序，pgvector 存储向量，未实现 ANN 大规模检索性能优化。
- Python 同步诊断取消在步骤边界生效；取消后拒绝结果提交，不声称立即中断所有在途系统调用。
- 原生 HTML 不参与回答渲染；当前为纯文本显示，未提供富 Markdown 展示。
- 前端 OpenAPI 自动生成用于请求模型，响应视图类型仍在 TypeScript 中维护，后续应补全响应 schema 后一并生成。
- worker 同时处理支持任务和索引，小规模演示适用，持续高任务流量下可将索引拆成独立 worker。
- 录制采用每秒一帧并编码为三分钟视频，无配音；操作与画面均来自运行中的应用。

## 工具环境

Docker Engine 已由用户启动。Playwright 浏览器下载遇到网络超时，改用本机已安装的 Chrome（通过 CHROME_PATH 指定）完成浏览器验收；没有跳过验收。

测试依赖当前存在 Starlette TestClient/httpx 的弃用提示，不影响本次通过结果；升级测试传输库可单独处理。
