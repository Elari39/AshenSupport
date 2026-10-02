<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { NAlert } from "naive-ui";
import { api } from "../api/client";
import type { Usage } from "../api/types";
const data = ref<Usage | null>(null),
  error = ref("");
const days = computed(() => {
  const result = new Map<
    string,
    { calls: number; failed: number; cost: number | null }
  >();
  for (const row of data.value?.items ?? []) {
    const key = row.created_at.slice(0, 10),
      day = result.get(key) ?? { calls: 0, failed: 0, cost: 0 };
    day.calls++;
    if (!row.success) day.failed++;
    day.cost =
      day.cost === null || row.cost === null ? null : day.cost + row.cost;
    result.set(key, day);
  }
  return [...result.entries()];
});
function duration(start: string | null, end: string | null) {
  return start && end
    ? `${((Date.parse(end) - Date.parse(start)) / 1000).toFixed(1)} s`
    : "未知";
}
onMounted(async () => {
  try {
    data.value = await api<Usage>("/admin/usage");
  } catch (e) {
    error.value = String(e);
  }
});
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">OBSERVABILITY</span>
      <h1>看见调用，也看见成本。</h1>
      <p>
        最近 2,000 次在线请求与 500 个执行批次。缺失计价或 usage 时标记未知。
      </p>
    </div>
  </div>
  <NAlert v-if="error" type="error">{{ error }}</NAlert>
  <section class="panel list-panel">
    <h2>每日汇总（UTC）</h2>
    <div v-for="[day, value] in days" :key="day" class="list-row">
      <strong>{{ day }}</strong
      ><span
        >{{ value.calls }} 次 · {{ value.failed }} 失败 · 估算费用
        {{ value.cost === null ? "未知" : value.cost.toFixed(6) }}</span
      >
    </div>
    <p v-if="!days.length" class="empty">
      暂无在线调用记录。fake provider 不产生模型费用。
    </p>
    <div class="table-scroll">
      <table v-if="data?.items.length">
        <thead>
          <tr>
            <th>模型 / 类型</th>
            <th>状态</th>
            <th>输入 / 输出 token</th>
            <th>延迟</th>
            <th>估算费用</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in data?.items" :key="row.id">
            <td>{{ row.model }} / {{ row.kind }}</td>
            <td>{{ row.success ? "成功" : "失败" }}</td>
            <td>
              {{ row.input_tokens ?? "未知" }} /
              {{ row.output_tokens ?? "未知" }}
            </td>
            <td>{{ row.elapsed_ms }} ms</td>
            <td>{{ row.cost ?? "未知" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <h2>任务延迟</h2>
    <div v-for="run in data?.runs.slice(0, 20)" :key="run.id" class="list-row">
      <small>{{ run.id.slice(0, 8) }}</small
      ><span
        >排队 {{ duration(run.created_at, run.started_at) }} · 执行
        {{ duration(run.started_at, run.finished_at) }}</span
      >
    </div>
  </section>
</template>
