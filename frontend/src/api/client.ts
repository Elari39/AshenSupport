let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    headers: {
      ...(!form && body !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
      ...(method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
    },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok)
    throw new ApiError(
      response.status,
      payload.error?.code ?? "http_error",
      payload.error?.message ?? "请求失败",
    );
  return payload as T;
}
export const statusLabel: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  waiting_input: "等待补充",
  waiting_approval: "等待审批",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  open: "待处理",
  closed: "已关闭",
  ready: "已索引",
  pending: "待审批",
  approve: "已批准",
  reject: "已拒绝",
};
export function displayStatus(value: string) {
  return statusLabel[value] ?? value;
}
