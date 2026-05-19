import type { CompileResult, Example, RunResult } from "../types/compiler";
import type { WorkspaceInfo } from "../types/workspace";

let BASE_URL = "http://127.0.0.1:8000";

const BUILTIN_DAG_EXAMPLE_NAME = "dag_optimization_demo";

const BUILTIN_DAG_EXAMPLE_SOURCE = `; NekoLang DAG optimization demo
; 这个示例故意重复计算相同表达式，用来观察四元式 DAG 如何合并公共子表达式。
(nya dag_optimization_demo
  (nyan ((a int) (b int) (c int) (d int) (e int) (f int) (g int)
         (h int) (i int) (j int) (k int) (m int) (n int) (p int)))
  (paw
    (:= a 6)
    (:= b 4)
    (:= c 3)

    (:= d (+ a b))
    (:= e (+ a b))
    (:= f (* d c))
    (:= g (* e c))

    (:= h (+ (* a b) (* a b)))

    (:= i (- f g))
    (:= j (+ d e))
    (:= k (+ d e))
    (:= m (* j k))
    (:= n (/ m c))
    (:= p (+ n (+ d e)))

    (meow d)
    (meow f)
    (meow h)
    (meow p)))`;

const BUILTIN_DAG_EXAMPLE: Example = {
  name: BUILTIN_DAG_EXAMPLE_NAME,
  description: "DAG 优化示例",
};

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
  backend: string = "auto",
  projectRoot?: string,
  sourcePath?: string,
  editedFiles?: Record<string, string>
): Promise<CompileResult> {
  try {
    return await request<CompileResult>("/api/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source,
        backend,
        ...(projectRoot ? { projectRoot } : {}),
        ...(sourcePath ? { sourcePath } : {}),
        ...(editedFiles && Object.keys(editedFiles).length > 0 ? { editedFiles } : {}),
      }),
    });
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 400) {
      const detail = error.detail || "编译管线返回了错误。";
      throw new CompileFailureError(`编译失败：${detail}`, detail, error.status);
    }
    throw error;
  }
}

export async function runProgram(
  source: string,
  backend: string = "auto",
  projectRoot?: string,
  sourcePath?: string,
  editedFiles?: Record<string, string>
): Promise<RunResult> {
  return request<RunResult>("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source,
      backend,
      ...(projectRoot ? { projectRoot } : {}),
      ...(sourcePath ? { sourcePath } : {}),
      ...(editedFiles && Object.keys(editedFiles).length > 0 ? { editedFiles } : {}),
    }),
  });
}

export async function getExamples(): Promise<Example[]> {
  const data = await request<{ examples: Example[] }>("/api/examples");
  const withoutBuiltin = data.examples.filter((example) => example.name !== BUILTIN_DAG_EXAMPLE_NAME);
  return [BUILTIN_DAG_EXAMPLE, ...withoutBuiltin];
}

export async function getExampleSource(name: string): Promise<string> {
  if (name === BUILTIN_DAG_EXAMPLE_NAME) return BUILTIN_DAG_EXAMPLE_SOURCE;
  const data = await request<{ source: string }>(`/api/examples/${name}`);
  return data.source;
}

export async function openWorkspace(folderPath: string): Promise<WorkspaceInfo> {
  return request<WorkspaceInfo>("/api/workspace/open", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: folderPath }),
  });
}

export async function readWorkspaceFile(
  rootPath: string,
  filePath: string
): Promise<{ source: string; path: string; relativePath: string }> {
  return request("/api/workspace/file", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rootPath, filePath }),
  });
}
