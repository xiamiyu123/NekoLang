"""Tests for neko.viz_api — FastAPI HTTP endpoints for NekoScope."""

import unittest

from starlette.testclient import TestClient


def _get_client():
    from neko.viz_api import app

    return TestClient(app)


VALID_SOURCE = "(nya t (nyan ((a int))) (paw (:= a 42) (meow a)))"
ERROR_SOURCE = "(nya t (paw (:= undefined_var 1)))"


class TestCompileEndpoint(unittest.TestCase):
    def test_compile_returns_full_result(self):
        client = _get_client()
        resp = client.post("/api/compile", json={"source": VALID_SOURCE, "backend": "llvm"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("tokens", data)
        self.assertIn("ast", data)
        self.assertIn("symbols", data)
        self.assertIn("quadruples", data)
        self.assertIn("quadrupleOptimization", data)
        self.assertIn("assembly", data)
        self.assertIn("errors", data)
        self.assertEqual(data["backend"], "llvm")
        self.assertGreater(len(data["tokens"]), 0)
        self.assertEqual(data["ast"]["nodeType"], "Program")
        self.assertGreater(len(data["symbols"]["entries"]), 0)
        self.assertGreater(len(data["quadruples"]), 0)
        self.assertEqual(data["quadrupleOptimization"]["beforeCount"], len(data["quadruples"]))

    def test_compile_with_errors(self):
        client = _get_client()
        resp = client.post("/api/compile", json={"source": ERROR_SOURCE})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data["errors"]), 0)
        self.assertEqual(data["errors"][0]["phase"], "Semantic")

    def test_compile_missing_source_returns_422(self):
        client = _get_client()
        resp = client.post("/api/compile", json={})
        self.assertEqual(resp.status_code, 422)


class TestTokensEndpoint(unittest.TestCase):
    def test_tokens_returns_token_list(self):
        client = _get_client()
        resp = client.post("/api/tokens", json={"source": VALID_SOURCE})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("tokens", data)
        token = data["tokens"][0]
        self.assertIn("type", token)
        self.assertIn("value", token)
        self.assertIn("line", token)
        self.assertIn("column", token)


class TestASTEndpoint(unittest.TestCase):
    def test_ast_returns_tree(self):
        client = _get_client()
        resp = client.post("/api/ast", json={"source": VALID_SOURCE})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("ast", data)
        self.assertEqual(data["ast"]["nodeType"], "Program")

    def test_ast_with_syntax_error_returns_400(self):
        client = _get_client()
        resp = client.post("/api/ast", json={"source": "(nya t (paw"})
        self.assertEqual(resp.status_code, 400)


class TestAssemblyEndpoint(unittest.TestCase):
    def test_assembly_returns_code(self):
        client = _get_client()
        resp = client.post("/api/assembly", json={"source": VALID_SOURCE, "backend": "llvm"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("assembly", data)
        self.assertIsInstance(data["assembly"], str)
        self.assertGreater(len(data["assembly"]), 0)

    def test_assembly_with_semantic_errors(self):
        client = _get_client()
        resp = client.post("/api/assembly", json={"source": ERROR_SOURCE, "backend": "llvm"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["assembly"], "")
        self.assertIn("errors", data)
        self.assertGreater(len(data["errors"]), 0)


class TestRunEndpoint(unittest.TestCase):
    def test_run_returns_program_output(self):
        client = _get_client()
        resp = client.post("/api/run", json={"source": VALID_SOURCE, "backend": "llvm"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["executablePath"], "expected a non-empty executable path")
        self.assertEqual(data["errors"], [])
        self.assertEqual(data["compileError"], "")

    def test_run_with_semantic_errors_returns_diagnostics(self):
        client = _get_client()
        resp = client.post("/api/run", json={"source": ERROR_SOURCE, "backend": "llvm"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["executablePath"], "")
        self.assertGreater(len(data["errors"]), 0)
        self.assertEqual(data["errors"][0]["phase"], "Semantic")


class TestExamplesEndpoint(unittest.TestCase):
    def test_list_examples(self):
        client = _get_client()
        resp = client.get("/api/examples")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("examples", data)
        self.assertGreater(len(data["examples"]), 0)
        names = [e["name"] for e in data["examples"]]
        self.assertIn("demo", names)
        self.assertIn("optimization_steps_demo", names)

    def test_get_example_source(self):
        client = _get_client()
        resp = client.get("/api/examples/demo")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("source", data)
        self.assertIn("nya", data["source"])

    def test_get_nonexistent_example_returns_404(self):
        client = _get_client()
        resp = client.get("/api/examples/nonexistent_xyz")
        self.assertEqual(resp.status_code, 404)


class TestExamplesIntegration(unittest.TestCase):
    def test_all_examples_compile_without_crash(self):
        client = _get_client()
        resp = client.get("/api/examples")
        self.assertEqual(resp.status_code, 200)
        examples = resp.json()["examples"]
        for ex in examples:
            src_resp = client.get(f"/api/examples/{ex['name']}")
            self.assertEqual(src_resp.status_code, 200)
            compile_resp = client.post(
                "/api/compile",
                json={"source": src_resp.json()["source"], "backend": "llvm"},
            )
            self.assertEqual(compile_resp.status_code, 200, f"Example '{ex['name']}' crashed")

    def test_example_names_are_url_safe(self):
        import re

        client = _get_client()
        resp = client.get("/api/examples")
        for ex in resp.json()["examples"]:
            self.assertRegex(ex["name"], re.compile(r"^[a-zA-Z0-9_-]+$"))
