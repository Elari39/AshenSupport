# 架构与取舍

```text
浏览器 Vue 3
  │ 同源 HTTP / SSE，Cookie + CSRF
  ▼
Nginx → FastAPI → PostgreSQL / pgvector
                      ▲
                      │ 任务领取、租约、步骤与事件
                 Python worker
                      ├─ 文档解析 / BM25 / 精确向量召回
                      ├─ fake 或在线 chat / embedding / rerank
                      └─ 模拟工具或固定目标 HTTPS 只读诊断
```

## 执行与持久化

API 创建 Task、Message、Run，并在同一事务写 queued 事件。worker 按创建时间领取任务，先锁 Task 再锁 Run，使用 skip locked 避免多 worker 相互阻塞。

Run 的 owner token 是 fencing token。所有步骤提交与终态提交必须持有当前 owner、有效租约和 running 状态。心跳延长租约，崩溃后可由新 owner 接手。取消先锁 Task，与审批和 worker 保持相同锁顺序。

Step 的 `(run_id,key)` 唯一。恢复会重放代码，但复用已提交步骤结果。外部模型调用完成、数据库提交前的崩溃无法避免重复调用和费用；不承诺 exactly-once。

队列放 PostgreSQL 是为了控制首期运维复杂度。任务和导入同一 worker 循环调度；首期小规模可用，持续任务流可能推迟索引，后续可拆索引 worker。

## 工单边界

模型只输出诊断结构。API 从结构与引用快照生成草稿，用户编辑增版；审批对版本校验并锁定 Task/Draft。审批记录和 Ticket 同事务插入，唯一约束防止重复。重复同向决定返回已有结果，反向决定冲突。

## 检索边界

文档版本包含 embedding 模型签名与维度。激活版本与内容快照分开；只有 active+enabled+同模型的 chunks 可检索。首期语料较小，向量保存在 pgvector，取出候选后在 Python 精确排序，不声称使用 ANN 索引。

BM25 按 chunk ID+内容的不可变快照缓存，LruCache 上限 16。向量和词法各 20，再 RRF、可选 rerank、最多 6 个上下文。

## 会话与网络

数据库仅保存会话 token 哈希；客户端持有 Cookie 与 CSRF。普通写入验证 Origin 与 CSRF。管理员无公开注册入口。

诊断使用独立的 HTTPSConnection：解析全部地址并拒绝非公网 IP；连接已经校验的 IP，同时以原主机名校验 TLS；禁重定向，截断过大响应。模型无法改 endpoint。

## 已知实现取舍

- SQLite 仅本地便利模式，不证明 PostgreSQL 行锁语义。
- SSE 轮询持久事件，首期每秒读取一次，适合低并发演示。
- 取消是在步骤边界禁止后续执行，在途同步 HTTP 不能即时强行终止。
- API 主模块首期聚合接口；继续增加业务时应按 auth/tasks/tickets/knowledge 路由拆分。
- 工单一个任务一个草稿，拒绝后保留历史，新需求创建新任务。
- 当前纯文本渲染，无原始 HTML 与远程图片能力。
