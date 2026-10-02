import { createApp } from "vue";
import { createPinia } from "pinia";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import Workspace from "./views/Workspace.vue";
import Tasks from "./views/Tasks.vue";
import Tickets from "./views/Tickets.vue";
import Knowledge from "./views/Knowledge.vue";
import Login from "./views/Login.vue";
import Usage from "./views/Usage.vue";
import "./style.css";
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/support" },
    { path: "/support", component: Workspace },
    { path: "/tasks", component: Tasks },
    { path: "/tickets", component: Tickets },
    { path: "/tickets/:id", component: Tickets },
    { path: "/admin/knowledge", component: Knowledge },
    { path: "/admin/usage", component: Usage },
    { path: "/login", component: Login },
    { path: "/:pathMatch(.*)*", redirect: "/support" },
  ],
});
createApp(App).use(createPinia()).use(router).mount("#app");
