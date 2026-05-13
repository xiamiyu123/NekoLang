import { describe, it, expect, vi, beforeEach } from "vitest";
import { compile, getExamples, getExampleSource, setBaseUrl } from "../client";

const mockCompileResponse = {
  source: "(nya t (paw (meow 0)))",
  tokens: [{ type: "program", value: "nya", line: 1, column: 2 }],
  ast: { nodeType: "Program", line: 1, column: 1, name: "t" },
  assembly: "define i32 @main() { ret i32 0 }",
  errors: [],
};

const mockExamplesResponse = {
  examples: [
    { name: "demo", description: "Demo" },
    { name: "fibonacci", description: "Fibonacci" },
  ],
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

  it("throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response('{"detail":"Not Found"}', { status: 404 })
    );

    await expect(getExampleSource("nonexistent")).rejects.toThrow("404");
  });
});
