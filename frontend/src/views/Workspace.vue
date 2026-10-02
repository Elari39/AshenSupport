<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NInput,
  NSelect,
  NTag,
  NAlert,
  NDrawer,
  NDrawerContent,
  useMessage,
} from "naive-ui";
import { api, displayStatus } from "../api/client";
import type { Task, Draft } from "../api/types";
import type { components } from "../api/schema";
import { useSession } from "../stores/session";
const session = useSession(),
  route = useRoute(),
  router = useRouter(),
  toast = useMessage();
const project = ref("notes-of-ashen"),
  scenario = ref("rag"),
  mode = ref("sandbox"),
  target = ref<string | null>(null);
const input = ref(""),
  task = ref<Task | null>(null),
  recent = ref<Task[]>([]),
  busy = ref(false),
  error = ref(""),
  drawer = ref(false);
const editTitle = ref(""),
  editDescription = ref("");
let stream: EventSource | null = null;
let generation = 0;
const active = computed(() =>
  ["queued", "running"].includes(task.value?.status ?? ""),
);
const projectOptions = computed(() =>
  session.projects.map((p) => ({ label: p.name, value: p.id })),
);
const scenarios = [
  {
    id: "rag",
    title: "RAG 无法回答",
    detail: "主站正常，问答失败",
    question: "博客主站正常，但开启 RAG 后无法问答，请帮我排查。",
  },
  {
    id: "cache",
    title: "缓存服务异常",
    detail: "依赖故障与降级",
    question: "短链服务 Redis 不可用时，跳转和统计会有什么影响？",
  },
  {
    id: "unknown",
    title: "信息不足",
    detail: "尝试补问与证据边界",
    question: "我的服务好像坏了，请帮我查一下。",
  },
];
function stop() {
  stream?.close();
  stream = null;
}
async function load(id: string, connect = true) {
  const version = ++generation;
  const loaded = await api<Task>(`/tasks/${id}`);
  if (version !== generation) return;
  task.value = loaded;
  const recentTask = recent.value.find((item) => item.id === id);
  if (recentTask) Object.assign(recentTask, loaded);
  editTitle.value = loaded.draft?.title ?? "";
  editDescription.value = loaded.draft?.description ?? "";
  if (connect) {
    stop();
    if (["queued", "running"].includes(loaded.status)) {
      stream = new EventSource(
        `/api/v1/tasks/${id}/events?after=${loaded.events.at(-1)?.id ?? 0}`,
      );
      stream.onmessage = () => {
        void load(id, false).catch((e) => {
          error.value = String(e);
        });
      };
      stream.addEventListener("done", () => {
        stop();
        void load(id, false).catch((e) => {
          error.value = String(e);
        });
      });
    }
  }
}
async function refreshRecent() {
  recent.value = (await api<{ items: Task[] }>("/tasks")).items;
}
async function run(fn: () => Promise<void>) {
  busy.value = true;
  error.value = "";
  try {
    await fn();
    await refreshRecent();
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}
async function send() {
  if (!input.value.trim()) return;
  await run(async () => {
    if (task.value?.status === "waiting_input") {
      await api(`/tasks/${task.value.id}/messages`, "POST", {
        message: input.value,
      });
      await load(task.value.id);
    } else {
      const body: components["schemas"]["TaskInput"] = {
        project_id: project.value as "notes-of-ashen" | "ashen-courier",
        message: input.value,
        scenario: scenario.value as "rag" | "cache" | "unknown",
        mode: mode.value as "sandbox" | "live",
        target_id: target.value,
      };
      const created = await api<{ id: string }>("/tasks", "POST", body);
      await router.replace({ query: { task: created.id } });
    }
    input.value = "";
  });
}
async function action(name: string) {
  await run(async () => {
    await api(`/tasks/${task.value!.id}/${name}`, "POST");
    await load(task.value!.id);
  });
}
async function saveDraft() {
  await run(async () => {
    const draft = task.value!.draft!;
    await api<Draft>(`/ticket-drafts/${draft.id}`, "PATCH", {
      version: draft.version,
      title: editTitle.value,
      description: editDescription.value,
    });
    await load(task.value!.id);
  });
}
async function decide(decision: "approve" | "reject") {
  await run(async () => {
    const draft = task.value!.draft!;
    const result = await api<{ ticket_id: string | null }>(
      `/ticket-drafts/${draft.id}/decision`,
      "POST",
      {
        version: draft.version,
        decision,
        idempotency_key: crypto.randomUUID(),
      },
    );
    await load(task.value!.id);
    toast.success(result.ticket_id ? "工单已创建" : "已拒绝创建工单");
  });
}
async function reset() {
  stop();
  generation++;
  task.value = null;
  input.value = "";
  await router.replace({ query: {} });
}
watch(
  () => route.query.task,
  async (id) => {
    stop();
    try {
      if (typeof id === "string") await load(id);
      else {
        generation++;
        task.value = null;
      }
    } catch (e) {
      error.value = String(e);
    }
  },
);
onMounted(() => {
  void run(async () => {
    if (typeof route.query.task === "string") await load(route.query.task);
  });
});
onBeforeUnmount(() => {
  stop();
  generation++;
});
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">SUPPORT WORKSPACE</span>
      <h1>把问题，变成有据可查的下一步。</h1>
      <p>检索项目文档，核对诊断结果，再决定是否创建工单。</p>
    </div>
    <NButton class="mobile-only" @click="drawer = true">任务与来源</NButton>
  </div>
  <NAlert
    v-if="error"
    type="error"
    class="error-banner"
    closable
    @close="error = ''"
    >{{ error }}</NAlert
  >
  <div class="workspace">
    <aside class="panel sidebar">
      <div class="section-label">项目空间</div>
      <NSelect
        v-model:value="project"
        :options="projectOptions"
        aria-label="选择项目"
        :disabled="active"
      />
      <NButton block class="new-task" @click="reset">＋ 新建支持任务</NButton>
      <div class="section-label">最近任务</div>
      <button
        v-for="item in recent.slice(0, 8)"
        :key="item.id"
        class="recent-item"
        :class="{ selected: task?.id === item.id }"
        @click="router.push({ query: { task: item.id } })"
      >
        <span>{{ item.title }}</span
        ><small>{{ displayStatus(item.status) }}</small>
      </button>
      <p v-if="!recent.length" class="muted">你的第一个问题，从这里开始。</p>
      <div class="sidebar-note">
        所有工单写入都需要你的批准。沙盒诊断使用预置数据。
      </div>
    </aside>
    <section class="panel conversation" aria-label="支持对话">
      <div class="conversation-header">
        <strong>{{ task ? task.title : "新建支持任务" }}</strong
        ><NTag
          size="small"
          :type="task?.mode === 'live' ? 'warning' : 'success'"
          >{{
            (task?.mode ?? mode) === "sandbox" ? "模拟诊断" : "真实诊断"
          }}</NTag
        >
      </div>
      <div class="conversation-body">
        <template v-if="!task">
          <div class="welcome-symbol">✦</div>
          <h2>从一个具体问题开始</h2>
          <p class="muted">选择演示场景，或描述你遇到的问题。</p>
          <div class="scenario-grid">
            <button
              v-for="item in scenarios"
              :key="item.id"
              class="scenario"
              :class="{ selected: scenario === item.id }"
              @click="
                scenario = item.id;
                input = item.question;
                project =
                  item.id === 'cache' ? 'ashen-courier' : 'notes-of-ashen';
              "
            >
              <strong>{{ item.title }} ↗</strong
              ><small>{{ item.detail }}</small>
            </button>
          </div>
          <div v-if="session.identity?.role === 'admin'" class="admin-options">
            <NSelect
              v-model:value="mode"
              :options="[
                { label: '模拟诊断', value: 'sandbox' },
                { label: '真实诊断', value: 'live' },
              ]"
              aria-label="诊断模式"
            /><NSelect
              v-if="mode === 'live'"
              v-model:value="target"
              :options="
                session.identity.health_targets.map((id) => ({
                  label: id,
                  value: id,
                }))
              "
              placeholder="选择已配置目标"
            />
          </div>
        </template>
        <template v-else>
          <div
            v-for="message in task.messages"
            :key="message.id"
            class="message"
            :class="message.role"
          >
            <span class="message-role">{{
              message.role === "user" ? "你" : "AshenSupport"
            }}</span>
            <p>{{ message.content }}</p>
          </div>
          <div v-if="active" class="working" role="status">
            <span class="dot"></span>{{ displayStatus(task.status) }} ·
            检索与诊断事件会在右侧更新
          </div>
          <div v-if="task.result" class="answer-details">
            <template v-if="task.result.facts.length"
              ><h3>已知事实</h3>
              <ul>
                <li v-for="fact in task.result.facts" :key="fact">
                  {{ fact }}
                </li>
              </ul></template
            ><template v-if="task.result.causes.length"
              ><h3>可能原因</h3>
              <ul>
                <li v-for="cause in task.result.causes" :key="cause.text">
                  {{ cause.text }}
                </li>
              </ul></template
            ><template v-if="task.result.steps.length"
              ><h3>排障步骤</h3>
              <ol>
                <li v-for="step in task.result.steps" :key="step">
                  {{ step }}
                </li>
              </ol></template
            ><template v-if="task.result.missing_information.length"
              ><h3>需要补充</h3>
              <ul>
                <li v-for="item in task.result.missing_information" :key="item">
                  {{ item }}
                </li>
              </ul></template
            >
          </div>
          <div class="task-actions">
            <NButton
              v-if="task.status === 'completed' && !task.draft"
              :loading="busy"
              @click="action('ticket-draft')"
              >生成工单草稿</NButton
            ><NButton
              v-if="
                [
                  'queued',
                  'running',
                  'waiting_input',
                  'waiting_approval',
                ].includes(task.status)
              "
              @click="action('cancel')"
              >取消任务</NButton
            ><NButton
              v-if="task.status === 'failed' && task.runs.at(-1)?.retryable"
              @click="action('retry')"
              >重试任务</NButton
            ><NTag>{{ displayStatus(task.status) }}</NTag>
          </div>
          <div v-if="task.draft" class="approval-card">
            <span class="eyebrow">HUMAN APPROVAL</span>
            <h3>审核工单草稿</h3>
            <p>确认内容后再创建。此操作不会写入 GitHub。</p>
            <NInput
              v-model:value="editTitle"
              :input-props="{ 'aria-label': '工单标题' }"
              :disabled="task.draft.status !== 'pending'"
            /><NInput
              v-model:value="editDescription"
              type="textarea"
              :input-props="{ 'aria-label': '工单描述' }"
              :disabled="task.draft.status !== 'pending'"
            />
            <div v-if="task.draft.status === 'pending'" class="task-actions">
              <NButton :loading="busy" @click="saveDraft">保存修改</NButton
              ><NButton
                type="primary"
                :loading="busy"
                :disabled="
                  editTitle !== task.draft.title ||
                  editDescription !== task.draft.description
                "
                @click="decide('approve')"
                >批准并创建</NButton
              ><NButton :disabled="busy" @click="decide('reject')"
                >拒绝</NButton
              >
            </div>
            <NTag v-else>{{ displayStatus(task.draft.status) }}</NTag>
          </div>
        </template>
      </div>
      <form class="composer" @submit.prevent="send">
        <NInput
          v-model:value="input"
          type="textarea"
          placeholder="描述问题、错误现象与已经尝试的步骤…"
          :input-props="{ 'aria-label': '问题描述' }"
          :maxlength="4000"
          :autosize="{ minRows: 3, maxRows: 7 }"
          :disabled="active || (!!task && task.status !== 'waiting_input')"
        />
        <div class="composer-bottom">
          <small>不要输入密码、API Key 或其他机密信息</small
          ><NButton
            type="primary"
            attr-type="submit"
            :loading="busy"
            :disabled="
              active ||
              !input.trim() ||
              (!!task && task.status !== 'waiting_input')
            "
            >{{
              task?.status === "waiting_input" ? "提交补充" : "开始排查"
            }}
            ↗</NButton
          >
        </div>
      </form>
    </section>
    <aside class="panel evidence">
      <span class="section-label">执行记录</span>
      <p v-if="!task" class="muted">任务开始后，这里会展示实际执行的步骤。</p>
      <div v-for="item in task?.events" :key="item.id" class="event">
        <span class="event-dot"></span
        ><span>{{ item.payload.message ?? item.kind }}</span>
        <pre v-if="item.payload.observation">{{
          JSON.stringify(item.payload.observation, null, 2)
        }}</pre>
      </div>
      <h3>
        来源与证据 <span class="count">{{ task?.citations.length ?? 0 }}</span>
      </h3>
      <details
        v-for="citation in task?.citations"
        :key="citation.id"
        class="citation"
      >
        <summary>
          {{ citation.document
          }}<small
            >{{ citation.version }} · L{{ citation.line_start }}–{{
              citation.line_end
            }}</small
          >
        </summary>
        <strong>{{ citation.heading }}</strong>
        <p>{{ citation.content }}</p>
      </details>
      <p v-if="!task?.citations.length" class="muted">
        尚无引用。证据不足时，助手会明确说明。
      </p>
    </aside>
  </div>
  <NDrawer v-model:show="drawer" :width="340"
    ><NDrawerContent title="任务与来源">
      <h3>项目空间</h3>
      <NSelect v-model:value="project" :options="projectOptions" :disabled="active" aria-label="选择项目" />
      <NButton block class="new-task" @click="reset(); drawer = false">＋ 新建支持任务</NButton>
      <h3>最近任务</h3>
      <button
        v-for="item in recent"
        :key="item.id"
        class="recent-item"
        @click="
          router.push({ query: { task: item.id } });
          drawer = false;
        "
      >
        {{ item.title }}
      </button>
      <h3>执行记录</h3>
      <p v-for="item in task?.events" :key="item.id">
        {{ item.payload.message ?? item.kind }}
      </p>
      <h3>来源</h3>
      <details v-for="citation in task?.citations" :key="citation.id">
        <summary>{{ citation.document }} · L{{ citation.line_start }}</summary>
        <p>{{ citation.content }}</p>
      </details></NDrawerContent
    ></NDrawer
  >
</template>
