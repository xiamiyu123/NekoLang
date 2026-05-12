"""Tests for nekgo project management tool."""

import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestNekgo(unittest.TestCase):
    def _run_nekgo(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, "-m", "neko.nekgo_cli", *args],
            capture_output=True,
            text=True,
            cwd=cwd or REPO_ROOT,
        )

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

    def test_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "hello", cwd=tmpdir)
            proj = os.path.join(tmpdir, "hello")

            result = self._run_nekgo("build", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("编译成功", result.stdout)
            self.assertTrue(os.path.isfile(os.path.join(proj, "build", "hello")))

    def test_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._run_nekgo("new", "hello", cwd=tmpdir)
            proj = os.path.join(tmpdir, "hello")

            result = self._run_nekgo("run", cwd=proj)
            self.assertEqual(result.returncode, 0)
            self.assertIn("42", result.stdout)
            self.assertTrue(os.path.isfile(os.path.join(proj, "build", "hello")))

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


if __name__ == "__main__":
    unittest.main()
