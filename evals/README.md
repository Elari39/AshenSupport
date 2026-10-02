# 评估数据与人工复核

cases.json 当前是 80 条未人工复核的案例，dev=50、test=30。首期验证运行器、引用 ID 契约与检索路径；结果不代表真实 AI 准确率。

正式实验前：人工校对问题与参考答案、确认语料版本，冻结 test 分组；后续只在 dev 上调整参数。不得反复修改 test 以提高分数。

运行报告后，在 backend 生成对应的人工复核模板：

```sh
uv run python -m app.score ../evals/reports/<report>.json
```

填写 `.review.json` 的 reviewer、human_reviewed、answer_correct、citations_supported 和 refusal_or_clarification_correct。只对适用指标填写布尔值，其余留 null。gold_evidence 使用 `document`、`line_start`、`line_end` 的来源行号区间。随后：

```sh
uv run python -m app.score ../evals/reports/<report>.json --annotations ../evals/reports/<report>.review.json
```

评分器校验报告哈希与唯一案例 ID，忽略未复核数据；输出分子分母、Recall@5 和人工正确性指标。gold_evidence 是相关证据区间，Recall@5 统计其中被前五个 chunk 覆盖的比例。该指标不等同于精确率，也不证明回答引用支持。

在线重排未配置时不运行。在线服务需显式 ASHEN_PROVIDER=online 和 --provider online，普通 CI 永远只运行 fake。
