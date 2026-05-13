"""Tests for nekgo project management tool."""

import os
import socket
import socketserver
import tempfile
import textwrap
import threading
import unittest

import pytest

from neko import nekgo_cli
from tests._cli_support import run_cli_main
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestNekgo(unittest.TestCase):
    def _run_nekgo(self, *args, cwd=None):
        return run_cli_main(nekgo_cli.main, args, cwd or REPO_ROOT, subprocess_module=nekgo_cli.subprocess)

    def test_new_creates_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run_nekgo("new", "testproj", cwd=tmpdir)
            self.assertEqual(result.returncode, 0)
            self.assertIn("已创建", result.stdout)

            proj = os.path.join(tmpdir, "testproj")
            self.assertTrue(os.path.isdir(proj))
            self.assertTrue(os.path.isfile(os.path.join(proj, "Neko.toml")))
            self.assertTrue(os.path.isfile(os.path.join(proj, "src", "main.neko")))
            self.assertTrue(os.path.isdir(os.path.join(proj, "build")))
            self.assertTrue(os.path.isfile(os.path.join(proj, ".gitignore")))
            with open(os.path.join(proj, "Neko.toml"), "r", encoding="utf-8") as f:
                toml_text = f.read()
            self.assertIn("[c]", toml_text)
            self.assertIn("auto_discover = true", toml_text)
            self.assertIn("sources = []", toml_text)

    def test_new_rejects_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "existing"))
            result = self._run_nekgo("new", "existing", cwd=tmpdir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("已存在", result.stdout)

    @pytest.mark.slow
    def test_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "hello", cwd=tmpdir)
            proj = os.path.join(tmpdir, "hello")

            result = self._run_nekgo("build", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("编译成功", result.stdout)
            self.assertTrue(os.path.isfile(os.path.join(proj, "build", "hello")))

    @pytest.mark.slow
    def test_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "hello", cwd=tmpdir)
            proj = os.path.join(tmpdir, "hello")

            result = self._run_nekgo("run", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("42", result.stdout)
            self.assertTrue(os.path.isfile(os.path.join(proj, "build", "hello")))

    @pytest.mark.slow
    def test_run_with_args(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "args_test", cwd=tmpdir)
            proj = os.path.join(tmpdir, "args_test")

            with open(os.path.join(proj, "src", "main.neko"), "w") as f:
                f.write(
                    "(program args_test "
                    "(var ((count int) (value int))) "
                    "(begin (:= count (argc)) (:= value (argv-int 0)) "
                    "(print count) (print value)))"
                )

            result = self._run_nekgo("run", "--", "99", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "1\n99")
            self.assertTrue(os.path.isfile(os.path.join(proj, "build", "args_test")))

    @pytest.mark.slow
    def test_run_ephemeral_keeps_build_directory_clean(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "ephemeral_test", cwd=tmpdir)
            proj = os.path.join(tmpdir, "ephemeral_test")

            result = self._run_nekgo("run", "--ephemeral", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("42", result.stdout)
            self.assertFalse(os.path.exists(os.path.join(proj, "build", "ephemeral_test")))

    def test_build_fails_without_toml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run_nekgo("build", cwd=tmpdir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Neko.toml", result.stdout)

    def test_no_command_shows_help(self):
        result = self._run_nekgo()
        self.assertEqual(result.returncode, 1)

    def test_clean_removes_build_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "clean_test", cwd=tmpdir)
            proj = os.path.join(tmpdir, "clean_test")
            build_dir = os.path.join(proj, "build")
            self.assertTrue(os.path.isdir(build_dir))

            result = self._run_nekgo("clean", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("已清理", result.stdout)
            self.assertFalse(os.path.exists(build_dir))

    def test_clean_when_no_build_directory(self):
        import shutil

        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "noclean", cwd=tmpdir)
            proj = os.path.join(tmpdir, "noclean")
            shutil.rmtree(os.path.join(proj, "build"))

            result = self._run_nekgo("clean", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("不存在", result.stdout)

    def test_clean_requires_project_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = os.path.join(tmpdir, "build")
            os.makedirs(build_dir)
            with open(os.path.join(build_dir, "keep.txt"), "w", encoding="utf-8") as f:
                f.write("keep me")

            result = self._run_nekgo("clean", cwd=tmpdir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Neko.toml", result.stdout)
            self.assertTrue(os.path.isdir(build_dir))

    def test_run_tests_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "testpass", cwd=tmpdir)
            proj = os.path.join(tmpdir, "testpass")

            os.makedirs(os.path.join(proj, "tests"), exist_ok=True)
            with open(os.path.join(proj, "tests", "test_basic.neko"), "w", encoding="utf-8") as f:
                f.write("(nya test_basic (nyan ((x int))) (paw (:= x 1) (meow x)))")

            result = self._run_nekgo("test", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("通过", result.stdout)
            self.assertIn("1 通过", result.stdout)

    def test_run_tests_can_import_from_src_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "testimport", cwd=tmpdir)
            proj = os.path.join(tmpdir, "testimport")

            os.makedirs(os.path.join(proj, "tests"), exist_ok=True)
            with open(os.path.join(proj, "src", "utils.neko"), "w", encoding="utf-8") as f:
                f.write("(function forty-two () int\n  (return 42))\n")
            with open(os.path.join(proj, "tests", "use_src.neko"), "w", encoding="utf-8") as f:
                f.write(
                    "(import utils)\n"
                    "(program use_src\n"
                    "  (var ((x int)))\n"
                    "  (begin\n"
                    "    (:= x (forty-two))\n"
                    "    (print x)))\n"
                )

            result = self._run_nekgo("test", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("1 通过", result.stdout)

    @pytest.mark.slow
    def test_build_parse_error_returns_formatted_message(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "badbuild", cwd=tmpdir)
            proj = os.path.join(tmpdir, "badbuild")

            with open(os.path.join(proj, "src", "main.neko"), "w", encoding="utf-8") as f:
                f.write("(invalid syntax here")

            result = self._run_nekgo("build", cwd=proj)
            self.assertEqual(result.returncode, 1)
            self.assertIn("[Parser]", result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_run_tests_fails_on_compile_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "testfail", cwd=tmpdir)
            proj = os.path.join(tmpdir, "testfail")

            os.makedirs(os.path.join(proj, "tests"), exist_ok=True)
            with open(os.path.join(proj, "tests", "test_bad.neko"), "w", encoding="utf-8") as f:
                f.write("(invalid syntax here")

            result = self._run_nekgo("test", cwd=proj)
            self.assertEqual(result.returncode, 1)
            self.assertIn("失败", result.stdout)

    def test_run_tests_semantic_failure_keeps_detailed_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "semanticfail", cwd=tmpdir)
            proj = os.path.join(tmpdir, "semanticfail")

            os.makedirs(os.path.join(proj, "tests"), exist_ok=True)
            with open(os.path.join(proj, "tests", "semantic_bad.neko"), "w", encoding="utf-8") as f:
                f.write(
                    "(program semantic_bad\n"
                    "  (var ((x int)))\n"
                    "  (begin\n"
                    "    (:= x (missing 1))\n"
                    "    (print x)))\n"
                )

            result = self._run_nekgo("test", cwd=proj)
            self.assertEqual(result.returncode, 1)
            self.assertIn("--- semantic_bad.neko ---", result.stdout)
            self.assertIn("未定义的函数 'missing'", result.stdout)
            self.assertNotIn("\n1\n", result.stdout)

    def test_run_tests_uses_custom_entry_directory_as_import_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "customentry", cwd=tmpdir)
            proj = os.path.join(tmpdir, "customentry")

            os.makedirs(os.path.join(proj, "app"), exist_ok=True)
            os.makedirs(os.path.join(proj, "tests"), exist_ok=True)
            with open(os.path.join(proj, "Neko.toml"), "w", encoding="utf-8") as f:
                f.write('[project]\nname = "customentry"\nentry = "app/main.neko"\n')
            with open(os.path.join(proj, "app", "utils.neko"), "w", encoding="utf-8") as f:
                f.write("(function forty-two () int\n  (return 42))\n")
            with open(os.path.join(proj, "app", "main.neko"), "w", encoding="utf-8") as f:
                f.write(
                    "(import utils)\n"
                    "(program customentry\n"
                    "  (var ((x int)))\n"
                    "  (begin\n"
                    "    (:= x (forty-two))\n"
                    "    (print x)))\n"
                )
            with open(os.path.join(proj, "tests", "use_app.neko"), "w", encoding="utf-8") as f:
                f.write(
                    "(import utils)\n"
                    "(program use_app\n"
                    "  (var ((x int)))\n"
                    "  (begin\n"
                    "    (:= x (forty-two))\n"
                    "    (print x)))\n"
                )

            result = self._run_nekgo("test", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("1 通过", result.stdout)

    def test_run_tests_match_run_import_resolution_for_same_module_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "shadowimport", cwd=tmpdir)
            proj = os.path.join(tmpdir, "shadowimport")

            os.makedirs(os.path.join(proj, "tests"), exist_ok=True)
            with open(os.path.join(proj, "utils.neko"), "w", encoding="utf-8") as f:
                f.write("(function forty-two () string\n  (return \"wrong\"))\n")
            with open(os.path.join(proj, "src", "utils.neko"), "w", encoding="utf-8") as f:
                f.write("(function forty-two () int\n  (return 42))\n")
            with open(os.path.join(proj, "tests", "use_src.neko"), "w", encoding="utf-8") as f:
                f.write(
                    "(import utils)\n"
                    "(program use_src\n"
                    "  (var ((x int)))\n"
                    "  (begin\n"
                    "    (:= x (forty-two))\n"
                    "    (print x)))\n"
                )

            result = self._run_nekgo("test", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("1 通过", result.stdout)

    def test_run_tests_no_tests_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "notestdir", cwd=tmpdir)
            proj = os.path.join(tmpdir, "notestdir")

            result = self._run_nekgo("test", cwd=proj)
            self.assertEqual(result.returncode, 1)
            self.assertIn("tests/", result.stdout)

    def test_run_tests_empty_tests_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "emptytests", cwd=tmpdir)
            proj = os.path.join(tmpdir, "emptytests")
            os.makedirs(os.path.join(proj, "tests"), exist_ok=True)

            result = self._run_nekgo("test", cwd=proj)
            self.assertEqual(result.returncode, 0)

    def test_load_project_config_auto_discovers_c_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "autoc", cwd=tmpdir)
            proj = os.path.join(tmpdir, "autoc")
            os.makedirs(os.path.join(proj, "csrc", "nested"), exist_ok=True)
            for rel_path in ("csrc/alpha.c", "csrc/nested/beta.c"):
                with open(os.path.join(proj, rel_path), "w", encoding="utf-8") as f:
                    f.write("int dummy(void) { return 1; }\n")

            project, c_build = nekgo_cli._load_project_config(proj)
            self.assertEqual(project["name"], "autoc")
            self.assertEqual(
                c_build.source_paths,
                tuple(sorted(
                    [
                        os.path.abspath(os.path.join(proj, "csrc", "alpha.c")),
                        os.path.abspath(os.path.join(proj, "csrc", "nested", "beta.c")),
                    ]
                )),
            )
            self.assertIn(os.path.abspath(os.path.join(proj, "csrc")), c_build.include_dirs)

    def test_load_project_config_merges_explicit_c_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "mergec", cwd=tmpdir)
            proj = os.path.join(tmpdir, "mergec")
            os.makedirs(os.path.join(proj, "csrc", "include"), exist_ok=True)
            os.makedirs(os.path.join(proj, "native"), exist_ok=True)
            with open(os.path.join(proj, "native", "extra.c"), "w", encoding="utf-8") as f:
                f.write("int extra(void) { return 7; }\n")
            with open(os.path.join(proj, "Neko.toml"), "w", encoding="utf-8") as f:
                f.write(
                    textwrap.dedent(
                        """
                        [project]
                        name = "mergec"
                        entry = "src/main.neko"

                        [c]
                        auto_discover = false
                        sources = ["native/extra.c"]
                        include_dirs = ["native/include"]
                        library_dirs = ["vendor/lib"]
                        libraries = ["m", "ssl"]
                        """
                    ).strip()
                    + "\n"
                )

            _, c_build = nekgo_cli._load_project_config(proj)
            self.assertEqual(c_build.source_paths, (os.path.abspath(os.path.join(proj, "native", "extra.c")),))
            self.assertIn(os.path.abspath(os.path.join(proj, "csrc")), c_build.include_dirs)
            self.assertIn(os.path.abspath(os.path.join(proj, "csrc", "include")), c_build.include_dirs)
            self.assertIn(os.path.abspath(os.path.join(proj, "native", "include")), c_build.include_dirs)
            self.assertEqual(c_build.library_dirs, (os.path.abspath(os.path.join(proj, "vendor", "lib")),))
            self.assertEqual(c_build.libraries, ("m", "ssl"))

    @pytest.mark.slow
    def test_build_links_with_explicit_include_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "includec", cwd=tmpdir)
            proj = os.path.join(tmpdir, "includec")
            os.makedirs(os.path.join(proj, "native", "include"), exist_ok=True)
            os.makedirs(os.path.join(proj, "native", "src"), exist_ok=True)
            with open(os.path.join(proj, "Neko.toml"), "w", encoding="utf-8") as f:
                f.write(
                    textwrap.dedent(
                        """
                        [project]
                        name = "includec"
                        entry = "src/main.neko"

                        [c]
                        auto_discover = false
                        sources = ["native/src/demo.c"]
                        include_dirs = ["native/include"]
                        library_dirs = []
                        libraries = []
                        """
                    ).strip()
                    + "\n"
                )
            with open(os.path.join(proj, "native", "include", "demo.h"), "w", encoding="utf-8") as f:
                f.write("int neko_demo_value(void);\n")
            with open(os.path.join(proj, "native", "src", "demo.c"), "w", encoding="utf-8") as f:
                f.write('#include "demo.h"\nint neko_demo_value(void) { return 29; }\n')
            with open(os.path.join(proj, "src", "main.neko"), "w", encoding="utf-8") as f:
                f.write(
                    '(program includec (var ((x int))) (begin (extern neko_demo_value () int) (:= x (neko_demo_value)) (print x)))'
                )

            result = self._run_nekgo("run", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "29")

    def test_load_project_config_rejects_missing_explicit_c_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "badc", cwd=tmpdir)
            proj = os.path.join(tmpdir, "badc")
            with open(os.path.join(proj, "Neko.toml"), "w", encoding="utf-8") as f:
                f.write(
                    textwrap.dedent(
                        """
                        [project]
                        name = "badc"
                        entry = "src/main.neko"

                        [c]
                        auto_discover = false
                        sources = ["missing.c"]
                        include_dirs = []
                        library_dirs = []
                        libraries = []
                        """
                    ).strip()
                    + "\n"
                )

            with self.assertRaises(SystemExit) as exc:
                nekgo_cli._load_project_config(proj)
            self.assertIn("missing.c", str(exc.exception))

    @pytest.mark.slow
    def test_build_verbose_lists_project_c_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "verbosec", cwd=tmpdir)
            proj = os.path.join(tmpdir, "verbosec")
            os.makedirs(os.path.join(proj, "csrc"), exist_ok=True)
            with open(os.path.join(proj, "src", "main.neko"), "w", encoding="utf-8") as f:
                f.write(
                    '(program verbosec (var ((x int))) (begin (extern neko_demo_value () int) (:= x (neko_demo_value)) (print x)))'
                )
            with open(os.path.join(proj, "csrc", "demo.c"), "w", encoding="utf-8") as f:
                f.write("int neko_demo_value(void) { return 17; }\n")

            result = self._run_nekgo("build", "--verbose", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("Project C sources:", result.stdout)
            self.assertIn("demo.c", result.stdout)
            self.assertIn("Running: clang", result.stdout)

    @pytest.mark.slow
    def test_build_with_project_c_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "projectc", cwd=tmpdir)
            proj = os.path.join(tmpdir, "projectc")
            os.makedirs(os.path.join(proj, "csrc"), exist_ok=True)
            with open(os.path.join(proj, "src", "main.neko"), "w", encoding="utf-8") as f:
                f.write(
                    '(program projectc (var ((x int))) (begin (extern neko_demo_value () int) (:= x (neko_demo_value)) (print x)))'
                )
            with open(os.path.join(proj, "csrc", "demo.c"), "w", encoding="utf-8") as f:
                f.write("int neko_demo_value(void) { return 17; }\n")

            result = self._run_nekgo("run", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "17")

    @pytest.mark.slow
    def test_build_missing_symbol_suggests_project_c_checks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "missingsymbol", cwd=tmpdir)
            proj = os.path.join(tmpdir, "missingsymbol")
            with open(os.path.join(proj, "src", "main.neko"), "w", encoding="utf-8") as f:
                f.write(
                    '(program missingsymbol (var ((x int))) (begin (extern neko_missing () int) (:= x (neko_missing)) (print x)))'
                )

            result = self._run_nekgo("build", cwd=proj)
            self.assertEqual(result.returncode, 1)
            self.assertIn("extern 名称", result.stderr)
            self.assertIn("csrc/", result.stderr)

    @pytest.mark.slow
    def test_run_tests_with_project_c_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "testprojectc", cwd=tmpdir)
            proj = os.path.join(tmpdir, "testprojectc")
            os.makedirs(os.path.join(proj, "csrc"), exist_ok=True)
            os.makedirs(os.path.join(proj, "tests"), exist_ok=True)
            with open(os.path.join(proj, "src", "libc.neko"), "w", encoding="utf-8") as f:
                f.write("(extern neko_demo_value () int)\n")
            with open(os.path.join(proj, "tests", "use_c.neko"), "w", encoding="utf-8") as f:
                f.write(
                    "(import libc)\n"
                    "(program use_c\n"
                    "  (var ((x int)))\n"
                    "  (begin\n"
                    "    (:= x (neko_demo_value))\n"
                    "    (print x)))\n"
                )
            with open(os.path.join(proj, "csrc", "demo.c"), "w", encoding="utf-8") as f:
                f.write("int neko_demo_value(void) { return 23; }\n")

            result = self._run_nekgo("test", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("1 通过", result.stdout)

    @pytest.mark.slow
    def test_run_socket_adapter_project(self):
        class EchoHandler(socketserver.StreamRequestHandler):
            def handle(self):
                incoming = self.rfile.readline().decode("utf-8").strip()
                response = f"pong:{incoming}\n".encode("utf-8")
                self.wfile.write(response)

        class LoopbackServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True

        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "socketdemo", cwd=tmpdir)
            proj = os.path.join(tmpdir, "socketdemo")
            os.makedirs(os.path.join(proj, "csrc"), exist_ok=True)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                host, port = sock.getsockname()

            server = LoopbackServer((host, port), EchoHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with open(os.path.join(proj, "src", "tcp.neko"), "w", encoding="utf-8") as f:
                    f.write(
                        "(extern neko_tcp_connect (string int) pointer)\n"
                        "(extern neko_tcp_send_text (pointer string) int)\n"
                        "(extern neko_tcp_recv_line (pointer) string)\n"
                        "(extern neko_tcp_close (pointer) int)\n"
                    )
                with open(os.path.join(proj, "src", "main.neko"), "w", encoding="utf-8") as f:
                    f.write(
                        "(import tcp)\n"
                        "(program socketdemo\n"
                        "  (var ((client pointer) (ok int) (reply string) (host string) (port int) (message string)))\n"
                        "  (begin\n"
                        "    (:= host (argv-string 0))\n"
                        "    (:= port (argv-int 1))\n"
                        "    (:= message (argv-string 2))\n"
                        "    (:= client (neko_tcp_connect host port))\n"
                        "    (:= ok (neko_tcp_send_text client message))\n"
                        "    (print ok)\n"
                        "    (:= reply (neko_tcp_recv_line client))\n"
                        "    (print reply)\n"
                        "    (:= ok (neko_tcp_close client))\n"
                        "    (print ok)))\n"
                    )
                with open(os.path.join(proj, "csrc", "neko_tcp_adapter.c"), "w", encoding="utf-8") as f:
                    f.write(
                        textwrap.dedent(
                            """
                            #include <arpa/inet.h>
                            #include <netinet/in.h>
                            #include <stdio.h>
                            #include <stdlib.h>
                            #include <string.h>
                            #include <sys/socket.h>
                            #include <sys/types.h>
                            #include <unistd.h>

                            struct neko_tcp_client {
                                int fd;
                            };

                            void *neko_tcp_connect(const char *host, int port) {
                                int fd = socket(AF_INET, SOCK_STREAM, 0);
                                if (fd < 0) {
                                    return NULL;
                                }

                                struct sockaddr_in addr;
                                memset(&addr, 0, sizeof(addr));
                                addr.sin_family = AF_INET;
                                addr.sin_port = htons((unsigned short)port);
                                if (inet_pton(AF_INET, host, &addr.sin_addr) != 1) {
                                    close(fd);
                                    return NULL;
                                }
                                if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
                                    close(fd);
                                    return NULL;
                                }

                                struct neko_tcp_client *client = malloc(sizeof(*client));
                                if (client == NULL) {
                                    close(fd);
                                    return NULL;
                                }
                                client->fd = fd;
                                return client;
                            }

                            int neko_tcp_send_text(void *handle, const char *text) {
                                if (handle == NULL || text == NULL) {
                                    return 0;
                                }
                                struct neko_tcp_client *client = handle;
                                size_t len = strlen(text);
                                if (send(client->fd, text, len, 0) < 0) {
                                    return 0;
                                }
                                if (send(client->fd, "\\n", 1, 0) < 0) {
                                    return 0;
                                }
                                return 1;
                            }

                            char *neko_tcp_recv_line(void *handle) {
                                if (handle == NULL) {
                                    char *empty = malloc(1);
                                    if (empty != NULL) {
                                        empty[0] = '\\0';
                                    }
                                    return empty;
                                }

                                struct neko_tcp_client *client = handle;
                                size_t cap = 256;
                                size_t len = 0;
                                char *buffer = malloc(cap);
                                if (buffer == NULL) {
                                    return NULL;
                                }

                                while (1) {
                                    char ch = '\\0';
                                    ssize_t n = recv(client->fd, &ch, 1, 0);
                                    if (n <= 0) {
                                        break;
                                    }
                                    if (ch == '\\n') {
                                        break;
                                    }
                                    if (len + 1 >= cap) {
                                        cap *= 2;
                                        char *grown = realloc(buffer, cap);
                                        if (grown == NULL) {
                                            free(buffer);
                                            return NULL;
                                        }
                                        buffer = grown;
                                    }
                                    buffer[len++] = ch;
                                }

                                buffer[len] = '\\0';
                                return buffer;
                            }

                            int neko_tcp_close(void *handle) {
                                if (handle == NULL) {
                                    return 0;
                                }
                                struct neko_tcp_client *client = handle;
                                int ok = close(client->fd) == 0;
                                free(client);
                                return ok ? 1 : 0;
                            }
                            """
                        ).strip()
                        + "\n"
                    )

                result = self._run_nekgo("run", "--", host, str(port), "miaow", cwd=proj)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout.strip(), "1\npong:miaow\n1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    @pytest.mark.slow
    def test_build_release_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "release_test", cwd=tmpdir)
            proj = os.path.join(tmpdir, "release_test")

            result = self._run_nekgo("build", "--mode", "release", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("编译成功", result.stdout)
            self.assertTrue(os.path.isfile(os.path.join(proj, "build", "release_test")))

    @pytest.mark.slow
    def test_build_debug_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "debug_test", cwd=tmpdir)
            proj = os.path.join(tmpdir, "debug_test")

            result = self._run_nekgo("build", "--mode", "debug", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("编译成功", result.stdout)


if __name__ == "__main__":
    unittest.main()
