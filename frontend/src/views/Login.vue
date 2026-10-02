<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { NInput, NButton, NAlert } from "naive-ui";
import { useSession } from "../stores/session";
const session = useSession(),
  router = useRouter(),
  username = ref(""),
  password = ref(""),
  error = ref(""),
  busy = ref(false);
async function submit() {
  busy.value = true;
  try {
    await session.login(username.value, password.value);
    password.value = "";
    await router.push("/admin/knowledge");
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <form class="panel login-panel" @submit.prevent="submit">
    <span class="eyebrow">ADMIN ACCESS</span>
    <h1>管理员登录</h1>
    <p>管理知识库、检查真实环境与查看用量。账号由部署者通过 CLI 创建。</p>
    <NAlert v-if="error" type="error">{{ error }}</NAlert
    ><label
      >账号<NInput
        v-model:value="username"
        autocomplete="username"
        :input-props="{ 'aria-label': '账号' }" /></label
    ><label
      >密码<NInput
        v-model:value="password"
        type="password"
        autocomplete="current-password"
        :input-props="{ 'aria-label': '密码' }" /></label
    ><NButton type="primary" attr-type="submit" block :loading="busy"
      >登录</NButton
    ><RouterLink to="/support">继续使用访客沙盒 →</RouterLink>
  </form>
</template>
