<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NConfigProvider, NMessageProvider, NButton, NAlert } from "naive-ui";
import type { GlobalThemeOverrides } from "naive-ui";
import { useSession } from "./stores/session";
const session = useSession();
const ready = ref(false),
  error = ref("");
onMounted(async () => {
  try {
    await session.init();
    ready.value = true;
  } catch (e) {
    error.value = String(e);
  }
});
const theme: GlobalThemeOverrides = {
  common: {
    primaryColor: "#ffe14a",
    primaryColorHover: "#ffea7a",
    primaryColorPressed: "#f4c828",
    primaryColorSuppl: "#ffe14a",
    textColorBase: "#171717",
    textColor1: "#171717",
    textColor2: "#292929",
    textColor3: "#515151",
    borderColor: "#171717",
    borderRadius: "0px",
    borderRadiusSmall: "0px",
    fontFamily: "Arial, 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif",
    fontWeightStrong: "800",
    successColor: "#157457",
    warningColor: "#96500b",
    errorColor: "#b52222",
  },
  Button: {
    border: "2px solid #171717", borderHover: "2px solid #171717", borderPressed: "2px solid #171717", borderFocus: "2px solid #171717",
    borderPrimary: "2px solid #171717", borderHoverPrimary: "2px solid #171717", borderPressedPrimary: "2px solid #171717", borderFocusPrimary: "2px solid #171717",
    textColorPrimary: "#171717", textColorHoverPrimary: "#171717", textColorPressedPrimary: "#171717", textColorFocusPrimary: "#171717",
    textColorHover: "#171717", textColorPressed: "#171717", textColorFocus: "#171717",
    fontWeight: "800", borderRadiusMedium: "0px", borderRadiusSmall: "0px", heightMedium: "40px",
  },
  Input: {border: "2px solid #171717", borderHover: "2px solid #171717", borderFocus: "2px solid #171717", boxShadowFocus: "4px 4px 0 #171717", color: "#ffffff", colorFocus: "#fffcef", textColor: "#171717", placeholderColor: "#626262"},
  InternalSelection: {border: "2px solid #171717", borderHover: "2px solid #171717", borderFocus: "2px solid #171717", borderActive: "2px solid #171717", boxShadowFocus: "3px 3px 0 #171717", boxShadowActive: "3px 3px 0 #171717", textColor: "#171717"},
  Tag: {borderRadius: "0px", textColor: "#171717", border: "2px solid #171717"},
  Drawer: {color: "#fffdf5", headerBorderBottom: "3px solid #171717", boxShadow: "-8px 0 0 #171717"},
  Message: {borderRadius: "0px", boxShadow: "5px 5px 0 #171717"},
};
</script>
<template>
  <NConfigProvider :theme-overrides="theme">
    <NMessageProvider>
      <a class="skip" href="#main">跳转到主要内容</a>
      <header class="app-header">
        <RouterLink to="/support" class="brand"
          ><span class="brand-symbol">A<span>✦</span></span
          ><span
            >AshenSupport<small>SUPPORT WITH EVIDENCE</small></span
          ></RouterLink
        >
        <nav aria-label="主导航">
          <RouterLink to="/support">工作台</RouterLink
          ><RouterLink to="/tasks">任务记录</RouterLink
          ><RouterLink to="/tickets">工单</RouterLink>
          <template v-if="session.identity?.role === 'admin'"
            ><RouterLink to="/admin/knowledge">知识库</RouterLink
            ><RouterLink to="/admin/usage">用量</RouterLink></template
          >
        </nav>
        <div class="account">
          <span class="dot"></span
          >{{ session.identity?.role === "admin" ? "管理员" : "访客沙盒"
          }}<RouterLink v-if="session.identity?.role !== 'admin'" to="/login"
            >登录</RouterLink
          ><NButton v-else size="small" @click="session.logout()">退出</NButton>
        </div>
      </header>
      <main id="main">
        <NAlert v-if="error" type="error" title="连接失败"
          >{{ error }}。请检查 API 与数据库后刷新页面。</NAlert
        ><RouterView v-else-if="ready" />
        <div v-else class="empty">正在连接工作台…</div>
      </main>
      <footer>
        有依据的诊断 · 有边界的执行
        <span
          >访客数据保留 7 天 ·
          {{
            session.identity?.provider === "fake"
              ? "确定性演示引擎（非真实 AI 效果）"
              : "在线模型"
          }}</span
        >
      </footer>
    </NMessageProvider>
  </NConfigProvider>
</template>
