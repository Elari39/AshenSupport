<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { NButton, NCheckbox, NTag, NAlert } from "naive-ui";
import { api, displayStatus } from "../api/client";
import type { Ticket } from "../api/types";
import { useSession } from "../stores/session";
const route = useRoute(),
  session = useSession(),
  rows = ref<Ticket[]>([]),
  detail = ref<Ticket | null>(null),
  sandbox = ref(false),
  error = ref("");
async function load() {
  try {
    if (typeof route.params.id === "string")
      detail.value = await api<Ticket>(`/tickets/${route.params.id}`);
    else {
      detail.value = null;
      rows.value = await api<Ticket[]>(`/tickets?sandbox=${sandbox.value}`);
    }
  } catch (e) {
    error.value = String(e);
  }
}
async function close() {
  try {
    await api(`/tickets/${detail.value!.id}`, "PATCH", { status: "closed" });
    await load();
  } catch (e) {
    error.value = String(e);
  }
}
onMounted(load);
watch(() => route.params.id, load);
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">TICKETS</span>
      <h1>从建议，到明确的待办。</h1>
      <p>只有经过人工批准的草稿，才会出现在这里。</p>
    </div>
  </div>
  <NAlert v-if="error" type="error">{{ error }}</NAlert>
  <section class="panel list-panel">
    <template v-if="detail"
      ><RouterLink to="/tickets">← 返回工单</RouterLink>
      <h2>{{ detail.title }}</h2>
      <NTag
        >{{ detail.sandbox ? "演示工单" : "正式工单" }} ·
        {{ displayStatus(detail.status) }}</NTag
      >
      <p class="preserve">{{ detail.description }}</p>
      <h3>建议步骤</h3>
      <ol>
        <li v-for="step in detail.evidence.result?.steps" :key="step">
          {{ step }}
        </li>
      </ol>
      <h3>证据</h3>
      <details v-for="citation in detail.evidence.citations" :key="citation.id">
        <summary>{{ citation.document }} · L{{ citation.line_start }}</summary>
        <p class="preserve">{{ citation.content }}</p>
      </details>
      <h3>审批记录</h3>
      <p v-for="a in detail.approvals" :key="a.created_at">
        {{ displayStatus(a.decision) }} ·
        {{ new Date(a.created_at).toLocaleString() }}
      </p>
      <div class="task-actions">
        <RouterLink :to="{ path: '/support', query: { task: detail.task_id } }"
          >查看来源任务</RouterLink
        ><NButton v-if="detail.status === 'open'" @click="close"
          >关闭工单</NButton
        >
      </div></template
    ><template v-else
      ><NCheckbox
        v-if="session.identity?.role === 'admin'"
        v-model:checked="sandbox"
        @update:checked="load"
        >显示演示工单</NCheckbox
      ><RouterLink
        v-for="ticket in rows"
        :key="ticket.id"
        :to="`/tickets/${ticket.id}`"
        class="list-row"
        ><div>
          <strong>{{ ticket.title }}</strong
          ><small
            >{{ ticket.sandbox ? "演示工单" : "正式工单" }} ·
            {{ new Date(ticket.created_at).toLocaleString() }}</small
          >
        </div>
        <NTag>{{ displayStatus(ticket.status) }}</NTag></RouterLink
      >
      <div v-if="!rows.length" class="empty">
        还没有工单。可以从已完成的支持任务生成草稿。
      </div></template
    >
  </section>
</template>
