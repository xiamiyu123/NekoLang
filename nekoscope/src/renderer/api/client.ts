import type { CompileResult, Example } from "../types/compiler";

let BASE_URL = "http://127.0.0.1:8000";

export function setBaseUrl(url: string) {
  BASE_URL = url;
}

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail: string = ""
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export class CompileFailureError extends Error {
  constructor(
    message: string,
    readonly detail: string,
    readonly status: number
  ) {
    super(message);
    this.name = "CompileFailureError";
  }
}

function getDetailMessage(payload: unknown): string {
  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload
  ) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return String(item);
        })
        .join("; ");
    }
  }
  return "";
}

async function readErrorDetail(res: Response): Promise<string> {
  try {
    return getDetailMessage(await res.clone().json());
  } catch {
    return res.text();
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const detail = await readErrorDetail(res);
    const suffix = detail ? `: ${detail}` : "";
    throw new ApiRequestError(`API error: ${res.status}${suffix}`, res.status, detail);
  }
  return res.json();
}

export async function compile(
  source: string,
  backend: string = "auto"
): Promise<CompileResult> {
  try {
    return await request<CompileResult>("/api/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, backend }),
    });
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 400) {
      const detail = error.detail || "编译管线返回了错误。";
      throw new CompileFailureError(`编译失败：${detail}`, detail, error.status);
    }
    throw error;
  }
}

export async function getExamples(): Promise<Example[]> {
  const data = await request<{ examples: Example[] }>("/api/examples");
  return data.examples;
}

export async function getExampleSource(name: string): Promise<string> {
  const data = await request<{ source: string }>(`/api/examples/${name}`);
  return data.source;
}
