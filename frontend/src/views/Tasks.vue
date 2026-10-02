<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NButton, NSelect, NAlert, NTag } from "naive-ui";
import { api, displayStatus } from "../api/client";
import type { Task } from "../api/types";
import { useSession } from "../stores/session";
const session = useSession(),
  rows = ref<Task[]>([]),
  status = ref<string | null>(null),
  project = ref<string | null>(null),
  cursor = ref<string | null>(null),
  error = ref("");
async function load(more = false) {
  try {
    const params = new URLSearchParams();
    if (status.value) params.set("status", status.value);
    if (project.value) params.set("project_id", project.value);
    if (more && cursor.value) params.set("cursor", cursor.value);
    const result = await api<{ items: Task[]; next_cursor: string | null }>(
      `/tasks?${params}`,
    );
    rows.value = more ? [...rows.value, ...result.items] : result.items;
    cursor.value = result.next_cursor;
  } catch (e) {
    error.value = String(e);
  }
}
onMounted(() => load());
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">HISTORY</span>
      <h1>每一次排查，都有迹可循。</h1>
      <p>回顾执行记录，继续待补充的任务。</p>
    </div>
    <RouterLink to="/support"
      ><NButton type="primary">新建任务</NButton></RouterLink
    >
  </div>
  <NAlert v-if="error" type="error">{{ error }}</NAlert>
  <section class="panel list-panel">
    <div class="filters">
      <NSelect
        v-model:value="project"
        clearable
        placeholder="全部项目"
        :options="session.projects.map((p) => ({ label: p.name, value: p.id }))"
        @update:value="load(false)"
      /><NSelect
        v-model:value="status"
        clearable
        placeholder="全部状态"
        :options="
          [
            'queued',
            'running',
            'waiting_input',
            'waiting_approval',
            'completed',
            'failed',
            'cancelled',
          ].map((s) => ({ label: displayStatus(s), value: s }))
        "
        @update:value="load(false)"
      />
    </div>
    <RouterLink
      v-for="task in rows"
      :key="task.id"
      :to="{ path: '/support', query: { task: task.id } }"
      class="list-row"
      ><div>
        <strong>{{ task.title }}</strong
        ><small
          >{{ task.project_id }} ·
          {{ new Date(task.created_at).toLocaleString() }} ·
          {{ task.mode === "sandbox" ? "模拟诊断" : "真实诊断" }}</small
        >
      </div>
      <NTag>{{ displayStatus(task.status) }}</NTag></RouterLink
    >
    <div v-if="!rows.length" class="empty">还没有符合条件的任务。</div>
    <NButton v-if="cursor" @click="load(true)">加载更多</NButton>
  </section>
</template>
