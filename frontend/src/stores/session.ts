import { defineStore } from "pinia";
import { ref } from "vue";
import { api, ApiError, setCsrf } from "../api/client";
import type { Identity, Project } from "../api/types";
export const useSession = defineStore("session", () => {
  const identity = ref<Identity | null>(null);
  const projects = ref<Project[]>([]);
  async function init() {
    try {
      identity.value = await api<Identity>("/me");
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
      await api("/sessions/guest", "POST");
      identity.value = await api<Identity>("/me");
    }
    setCsrf(identity.value.csrf_token);
    projects.value = await api<Project[]>("/projects");
  }
  async function login(username: string, password: string) {
    await api("/auth/login", "POST", { username, password });
    await init();
  }
  async function logout() {
    await api("/auth/logout", "POST");
    await init();
  }
  return { identity, projects, init, login, logout };
});
