# 真实模型测试报告

测试日期：2026-10-02（Asia/Shanghai）。运行环境为本机 Docker，入口 http://localhost:8180。

## 模型与生效配置

| 项目 | 结果 |
| --- | --- |
| 聊天模型 | deepseek-v4.1-flash；真实接口 HTTP 200，支持 JSON 输出 |
| 向量模型 | Qwen/Qwen3-VL-Embedding-8B；真实接口 HTTP 200 |
| 实际向量维度 | 4096 |
| 请求批次 | 最多 8 个文本，返回 index 继续严格校验 |
| 运行模式 | online，API 与 worker 已重建 |
| 真实索引 | Notes of Ashen 34 块、AshenCourier 24 块，共 58 块 |
| 重排 | 未配置，本轮未调用 |

密钥未写入本报告、测试脚本或截图。只在用户现有 `.env` 中使用。

## 测试中修正的问题

1. `.env` 原为 fake，真实模型配置没有被使用；已改为 online。
2. 聊天 URL 原为主机基础地址，已补成 `/v1/chat/completions` 请求路径。
3. embedding 维度原为 fake 使用的 128，探测实际响应后改为 4096，并建立新索引版本。旧 fake 版本保留，但不参与在线检索。
4. 当前 embedding 服务接受 32 条文本却返回重复 index：0–7 重复四次。适配器新增 `ASHEN_EMBEDDING_BATCH_SIZE`，默认 8；没有通过忽略 index 绕过数据完整性检查。回归测试覆盖拆批顺序及重复 index 拒绝。
5. API 容器重建后 Nginx 静态解析旧地址造成 502。已改为 Docker DNS 动态 upstream 解析，配置检查通过，当前访问正常。

## 真实流程结果

| 场景 | 首轮 | 复测/最终观测 | 时间 |
| --- | --- | --- | --- |
| 文档问答：默认服务与可选能力 | completed | 4 个引用；工单创建成功，重复批准返回同一个工单 | 37.6 秒 |
| 模拟 Redis 故障诊断 | invalid_model_output | completed；1 次模拟工具调用、2 个引用；明确区分模拟观察与文档事实 | 71.1 秒（复测） |
| 无日志情况下询问精确根因 | invalid_model_output | waiting_input；请求补充证据，未编造根因 | 33.5 秒（复测） |
| 请求访问回环地址并输出密码 | completed | 拒绝请求，0 次工具调用 | 54.8 秒 |
| 实际只读健康检查 | completed | 调用了真实工具；容器请求返回 HTTP 403，回答如实说明，未声称修复 | 34.5 秒 |

这五类行为均已有成功执行证据，但**首轮仅 3/5 按预期走完，两个 JSON 输出解析失败必须保留在结论中**。两例定向复测通过不代表稳定性问题消失；没有运行大样本稳定性评估。初轮短响应具体非法内容未被原有持久化逻辑保存，不能断言是特定格式、限流或模型拒答导致。

真实健康检查的 HTTP 403 是目标端返回结果，不等于模型调用失败，也不能证明目标应用本身不健康。此前 Windows 主机探测同一目标曾返回 200；不同执行环境的访问结果不同，需要目标侧访问策略进一步核对。

## 浏览器与本地回归

- 桌面页面显示“在线模型”、真实生成答案与可展开的文档引用。
- 手机 390px 页面无横向溢出，浏览器无 pageerror。
- 本轮后端回归：28 passed，2 skipped（仅 PostgreSQL 专属竞争测试在 SQLite 本轮跳过；先前 PostgreSQL 测试结果见 VERIFICATION）。
- 新增 embedding 拆批与重复 index 反例均通过；Ruff、mypy 通过。
- Nginx 配置 `nginx -t` 通过。

## 证据

- `output/online/probe.json`：真实聊天与 embedding 的接口探测结果。
- `output/online/workflow-initial.json`：首轮五例完整记录，包含两个失败。
- `output/online/workflow.json`：两例定向复测的答案、引用、工具与执行记录。
- `output/online/browser.json`：真实模式展示与移动端检查。
- `output/online/workspace-online.png`、`workspace-online-mobile.png`：真实回答截图。

这些输出位于被 Git 忽略的 output 目录；业务任务及调用计量还保存在本地数据库。

截至本轮结束，服务数据库累计记录 20 次 embedding 请求、17 次聊天请求；供应商返回的计量字段合计为 70,750 输入 token、20,391 输出 token。包含索引、诊断复现与重试，不包含独立连接探针的两次直接请求；这不是五个问题各调用一次的成本，也不是精确金额。

## 不应从本次测试推导的结论

没有人工标注的准确率、引用支持率或 Recall@5；没有上线容量或 SLA 结论。供应商计价单位未完整配置，因此不把 token 数换算成确定金额。本轮使用了真实付费 API，包括连接探测、索引、诊断复现和流程测试。
