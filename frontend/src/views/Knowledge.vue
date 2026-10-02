<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from "vue";
import { NButton, NSelect, NInput, NTag, NAlert } from "naive-ui";
import { api, displayStatus } from "../api/client";
import type { Document } from "../api/types";
import { useSession } from "../stores/session";
const session = useSession(),
  rows = ref<Document[]>([]),
  project = ref("notes-of-ashen"),
  label = ref("v1"),
  source = ref(""),
  files = ref<File[]>([]),
  error = ref(""),
  busy = ref(false),
  preview = ref<unknown>(null);
let timer: ReturnType<typeof setInterval> | undefined;
async function load() {
  try {
    rows.value = await api<Document[]>("/admin/documents");
  } catch (e) {
    error.value = String(e);
  }
}
async function upload() {
  busy.value = true;
  try {
    const form = new FormData();
    form.set("project_id", project.value);
    form.set("label", label.value);
    form.set("source", source.value);
    files.value.forEach((f) => form.append("files", f));
    await api("/admin/documents", "POST", form);
    await load();
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}
function selectFiles(e: Event) {
  files.value = Array.from((e.target as HTMLInputElement).files ?? []);
}
async function action(id: string, name: string) {
  try {
    if (name === "chunks")
      preview.value = await api(`/admin/documents/${id}/chunks`);
    else {
      await api(
        `/admin/documents/${id}${name === "reindex" ? "/reindex" : ""}`,
        name === "reindex" ? "POST" : "DELETE",
      );
      await load();
    }
  } catch (e) {
    error.value = String(e);
  }
}
onMounted(() => {
  if (session.identity?.role === "admin") {
    void load();
    timer = setInterval(() => {
      void load();
    }, 5000);
  }
});
onBeforeUnmount(() => clearInterval(timer));
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">KNOWLEDGE</span>
      <h1>让每个答案，都有来源。</h1>
      <p>维护项目文档与索引版本。新版本就绪后才会替换旧版本。</p>
    </div>
  </div>
  <NAlert v-if="session.identity?.role !== 'admin'" type="warning"
    >请以管理员身份登录。</NAlert
  ><template v-else
    ><NAlert v-if="error" type="error">{{ error }}</NAlert>
    <form class="panel import-form" @submit.prevent="upload">
      <NSelect
        v-model:value="project"
        :options="session.projects.map((p) => ({ label: p.name, value: p.id }))"
        aria-label="所属项目"
      /><NInput
        v-model:value="label"
        placeholder="版本标签"
        :input-props="{ 'aria-label': '版本标签' }"
      /><NInput
        v-model:value="source"
        placeholder="来源链接（可选，不会自动访问）"
        :input-props="{ 'aria-label': '来源链接' }"
      /><label class="file-input"
        >选择 Markdown / TXT<input
          type="file"
          accept=".md,.txt"
          multiple
          @change="selectFiles" /></label
      ><small>UTF-8 · 单文件 ≤ 2 MiB · 每次 ≤ 20 个</small
      ><NButton
        attr-type="submit"
        type="primary"
        :loading="busy"
        :disabled="!files.length"
        >导入并索引</NButton
      >
    </form>
    <section class="panel list-panel">
      <article v-for="doc in rows" :key="doc.id" class="document-row">
        <h3>
          {{ doc.logical_key }}
          <NTag size="small">{{ doc.enabled ? "启用" : "停用" }}</NTag>
        </h3>
        <small>{{ doc.project_id }}</small>
        <div v-for="version in doc.versions" :key="version.id" class="version">
          <strong>{{ version.label }}</strong> ·
          {{ displayStatus(version.status)
          }}<small>SHA-256 {{ version.content_hash }}</small
          ><NAlert v-if="version.error" type="error">{{
            version.error
          }}</NAlert>
        </div>
        <div class="task-actions">
          <NButton size="small" @click="action(doc.id, 'chunks')"
            >查看切块</NButton
          ><NButton size="small" @click="action(doc.id, 'reindex')"
            >重新索引</NButton
          ><NButton size="small" @click="action(doc.id, 'disable')"
            >停用</NButton
          >
        </div>
      </article>
      <p v-if="!rows.length" class="empty">还没有导入文档。</p>
    </section>
    <section v-if="preview" class="panel list-panel">
      <h2>切块预览</h2>
      <pre>{{ JSON.stringify(preview, null, 2) }}</pre>
    </section></template
  >
</template>
