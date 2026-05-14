import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  ApiRequestError,
  CompileFailureError,
  compile,
  getExamples,
  getExampleSource,
  runProgram,
  setBaseUrl,
} from "../client";

const mockCompileResponse = {
  source: "(nya t (paw (meow 0)))",
  tokens: [{ type: "program", value: "nya", line: 1, column: 2 }],
  ast: { nodeType: "Program", line: 1, column: 1, name: "t" },
  symbols: { entries: [{ name: "t", type: "program", category: "program", address: null, addressName: "t", scope: "global" }], constants: {} },
  quadruples: [{ op: "program", ob1: "t", ob2: "_", t: "_" }],
  assembly: "define i32 @main() { ret i32 0 }",
  errors: [],
  backend: "llvm",
};

const mockExamplesResponse = {
  examples: [
    { name: "demo", description: "Demo" },
    { name: "fibonacci", description: "Fibonacci" },
  ],
};

const mockRunResponse = {
  stdout: "42\n",
  stderr: "",
  exitCode: 0,
  timedOut: false,
  errors: [],
  compileError: "",
};

describe("API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setBaseUrl("http://localhost:8000");
  });

  it("compile returns typed result", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockCompileResponse), { status: 200 })
    );

    const result = await compile("(nya t (paw (meow 0)))");
    expect(result.tokens).toHaveLength(1);
    expect(result.ast.nodeType).toBe("Program");
    expect(result.symbols.entries).toHaveLength(1);
    expect(result.quadruples).toHaveLength(1);
    expect(result.errors).toHaveLength(0);
    expect(result.assembly).toContain("define");
  });

  it("compile passes backend parameter", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockCompileResponse), { status: 200 })
    );

    await compile("source", "llvm");
    const body = JSON.parse(fetchSpy.mock.calls[0][1]!.body as string);
    expect(body.backend).toBe("llvm");
  });

  it("compile reports backend compilation details instead of a generic API error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "[Parser] Line 1, Column 12: 期望 ')'" }),
        { status: 400 }
      )
    );

    await expect(compile("(nya t (paw")).rejects.toMatchObject({
      name: "CompileFailureError",
      message: expect.stringContaining("编译失败"),
      detail: expect.stringContaining("期望 ')'"),
    });
  });

  it("runProgram posts source and backend to run endpoint", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockRunResponse), { status: 200 })
    );

    const result = await runProgram("source", "llvm");
    expect(result.stdout).toBe("42\n");
    expect(result.exitCode).toBe(0);
    expect(fetchSpy.mock.calls[0][0]).toBe("http://localhost:8000/api/run");
    const body = JSON.parse(fetchSpy.mock.calls[0][1]!.body as string);
    expect(body).toMatchObject({ source: "source", backend: "llvm" });
  });

  it("getExamples returns list", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockExamplesResponse), { status: 200 })
    );

    const examples = await getExamples();
    expect(examples).toHaveLength(2);
    expect(examples[0].name).toBe("demo");
  });

  it("getExampleSource returns source string", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ source: "(nya t (paw 0))" }), { status: 200 })
    );

    const source = await getExampleSource("demo");
    expect(source).toContain("nya");
  });

  it("throws request error with backend detail on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response('{"detail":"Not Found"}', { status: 404 })
    );

    await expect(getExampleSource("nonexistent")).rejects.toMatchObject({
      name: "ApiRequestError",
      message: expect.stringContaining("404"),
      detail: "Not Found",
    });
  });
});
