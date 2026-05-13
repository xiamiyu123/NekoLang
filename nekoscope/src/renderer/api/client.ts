import type { CompileResult, Example } from "../types/compiler";

let BASE_URL = "http://127.0.0.1:8000";

export function setBaseUrl(url: string) {
  BASE_URL = url;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

export async function compile(
  source: string,
  backend: string = "auto"
): Promise<CompileResult> {
  return request<CompileResult>("/api/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, backend }),
  });
}

export async function getExamples(): Promise<Example[]> {
  const data = await request<{ examples: Example[] }>("/api/examples");
  return data.examples;
}

export async function getExampleSource(name: string): Promise<string> {
  const data = await request<{ source: string }>(`/api/examples/${name}`);
  return data.source;
}
