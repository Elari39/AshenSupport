# 运行手册

## 启动与诊断

`docker compose up -d --build` 后依次检查 `docker compose ps`、`docker compose logs --tail 100 migrate`、`docker compose logs --tail 100 worker`。API `/healthz` 验证数据库连接，不代表模型或索引已经就绪。

页面 403：核对浏览器来源与 ASHEN_ORIGIN，刷新 CSRF；生产 HTTPS 设置 ASHEN_SECURE_COOKIE=true。不要关闭校验解决配置错误。

任务排队不动：确认 worker 运行，查看 task_runs；进程中断后等待租约到期。三次恢复上限后任务失败，修复依赖再手动重试。

无引用：先确认索引 ready，文档启用，embedding 模型与维度一致。配置改变后重新索引；失败时旧版本仍保存，但与新模型不匹配的版本不会被检索。

在线 429：检查供应商额度和应用全局 daily_calls。每次重试也消耗额度。401/403 不重试，应修复服务端配置。

## 数据备份与恢复

使用 PostgreSQL 自带工具。示例不在命令里展开密码，利用容器内 PG 环境。

```powershell
docker compose exec -T db pg_dump -U ashen -d ashen -Fc -f /tmp/ashen-backup.dump
docker compose cp db:/tmp/ashen-backup.dump ./output/ashen-backup.dump
```

先创建 output 目录。备份含用户内容，仅存放在受控位置，不提交 Git。恢复演练必须使用新建的独立数据库，不能覆盖业务库：

```powershell
docker compose exec -T db createdb -U ashen ashen_restore_check
docker compose exec -T db pg_restore -U ashen -d ashen_restore_check /tmp/ashen-backup.dump
docker compose exec -T db psql -U ashen -d ashen_restore_check -c "SELECT count(*) FROM projects;"
```

重复演练时使用新的数据库名。确认需要清理后，只删除该演练数据库。升级前备份；只添加前向迁移，不改已发布迁移。

## 生产入口

默认 web 仅绑定回环地址。公网发布前设置 HTTPS 反向代理、ASHEN_ORIGIN、Secure Cookie，并按真实代理链配置客户端 IP。不能无条件相信客户端自带的 X-Forwarded-For；错误配置会让访客共享 IP 额度。

默认额度比较保守，演示前不要无限重试用光同一 IP 的额度。可通过服务端配置在隔离测试环境提高限额；不要清空生产审计数据解决问题。

## 清理和停机

worker 每小时清理过期访客及其任务、引用、草稿和工单。CLI `python -m app.cli cleanup` 可手动触发。管理员数据不受访客清理策略影响。

`docker compose down` 停止服务并保留卷。`down -v` 会删除数据库，只能用于明确可丢弃的测试环境。
