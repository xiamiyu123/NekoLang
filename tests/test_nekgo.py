"""Tests for nekgo project management tool."""

import os
import tempfile
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
