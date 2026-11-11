"""Deployment integration tests: every Git mutation uses disposable local repos."""

import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy.py"
REPO_SCRIPT = ROOT / "scripts" / "repo.py"
spec = importlib.util.spec_from_file_location("deploy_under_test", SCRIPT)
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)
GIT = shutil.which("git")
TOOLS_AVAILABLE = all(shutil.which(tool) for tool in ("git", "dpkg", "dpkg-deb", "dpkg-scanpackages"))


def isolated_environment(home, temporary):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update({
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / "config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        # This test process cannot contact an SSH/HTTP/remote-helper origin.
        "GIT_ALLOW_PROTOCOL": "file",
        "TMPDIR": str(temporary),
        "LC_ALL": "C",
        "SOURCE_DATE_EPOCH": "1700000000",
    })
    return environment


class ConfirmationTests(unittest.TestCase):
    def test_tty_requires_complete_yes(self):
        with mock.patch.object(deploy.sys.stdin, "isatty", return_value=True):
            with mock.patch("builtins.input", return_value="yes"):
                deploy.confirm_publish(False)
            for value in ("y", "YES", "no", ""):
                with self.subTest(answer=value), mock.patch("builtins.input", return_value=value):
                    with self.assertRaises(deploy.DeployError):
                        deploy.confirm_publish(False)

    def test_noninteractive_confirmation_requires_explicit_flag(self):
        with mock.patch.object(deploy.sys.stdin, "isatty", return_value=False):
            with self.assertRaises(deploy.DeployError):
                deploy.confirm_publish(False)
            deploy.confirm_publish(True)


@unittest.skipUnless(TOOLS_AVAILABLE, "需要 git / dpkg / dpkg-deb / dpkg-scanpackages")
class DeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory(prefix="mytweak-publish-fixtures-")
        cls.addClassCleanup(cls.fixtures.cleanup)
        cls.fixture_root = Path(cls.fixtures.name).resolve()
        home = cls.fixture_root / "home"
        temporary = cls.fixture_root / "temporary"
        home.mkdir()
        temporary.mkdir()
        environment = isolated_environment(home, temporary)
        debs = cls.fixture_root / "debs"
        debs.mkdir()
        for architecture, folder in (("iphoneos-arm", "rootful"), ("iphoneos-arm64", "archive/rootless")):
            source = cls.fixture_root / f"package-{architecture}"
            (source / "DEBIAN").mkdir(parents=True)
            (source / "DEBIAN" / "control").write_text(
                "Package: com.example.publish-test\nVersion: 1.0-1\n"
                f"Architecture: {architecture}\n"
                "Maintainer: Fixture <fixture@example.invalid>\n"
                "Description: No-op deployment fixture\nSection: Tweaks\n",
                encoding="utf-8",
            )
            payload = source / "usr" / "share" / "publish-test"
            payload.mkdir(parents=True)
            (payload / "fixture.txt").write_text("no-op test data\n", encoding="utf-8")
            destination = debs / folder / f"com.example.publish-test_1.0-1_{architecture}.deb"
            destination.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["dpkg-deb", "--build", "--root-owner-group", "-Zgzip", str(source), str(destination)],
                cwd=cls.fixture_root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, check=False,
            )
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
        cls.fixture_output = cls.fixture_root / "output"
        result = subprocess.run(
            [sys.executable, "-I", str(REPO_SCRIPT), "build", "--debs", str(debs),
             "--output", str(cls.fixture_output), "--config", str(ROOT / "repo.json")],
            cwd=cls.fixture_root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mytweak-publish-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.home = self.root / "home"
        self.scratch = self.root / "temporary"
        self.home.mkdir()
        self.scratch.mkdir()
        self.env = isolated_environment(self.home, self.scratch)
        self.project = self.root / "development"
        self.project.mkdir()
        self.remote = self.root / "origin.git"
        self.checked([GIT, "init", "--bare", str(self.remote)])
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Publish Test")
        self.git("config", "user.email", "publish-test@example.invalid")
        self.git("config", "commit.gpgSign", "false")
        (self.project / "scripts").mkdir()
        shutil.copyfile(SCRIPT, self.project / "scripts" / "deploy.py")
        shutil.copyfile(REPO_SCRIPT, self.project / "scripts" / "repo.py")
        shutil.copyfile(ROOT / "deploy.sh", self.project / "deploy.sh")
        (self.project / "development.txt").write_text("initial development content\n")
        (self.project / ".gitignore").write_text(".build/\n")
        self.git("add", ".")
        self.git("commit", "-m", "Development fixture")
        self.git("remote", "add", "origin", str(self.remote))

        self.output = self.project / ".build" / "repo"
        shutil.copytree(self.fixture_output, self.output)
        self.seed = self.root / "seed"
        self.git("worktree", "add", "--detach", str(self.seed), "HEAD")
        self.git("rm", "-r", "--", ".", cwd=self.seed)
        shutil.copytree(self.output, self.seed, dirs_exist_ok=True)
        # Model the historical polluted publishing branch without executing it.
        (self.seed / ".claude").mkdir()
        (self.seed / ".claude" / "settings.local.json").write_text('{"legacy": true}\n')
        (self.seed / "generate.sh").write_text("#!/bin/sh\nexit 97\n")
        (self.seed / "obsolete.html").write_text("obsolete\n")
        (self.seed / ".gitattributes").write_text("* -text\n")
        (self.seed / "CNAME").write_text("packages.example.invalid\n")
        self.git("add", "-A", cwd=self.seed)
        self.git("commit", "-m", "Historical Pages fixture", cwd=self.seed)
        self.baseline = self.git("rev-parse", "HEAD", cwd=self.seed).stdout.strip()
        self.git("branch", "gh-pages", self.baseline)
        self.git("push", "origin", "refs/heads/gh-pages:refs/heads/gh-pages")
        self.git("worktree", "remove", str(self.seed))

    def checked(self, command, *, cwd=None, env=None, input_data=None, success=True):
        result = subprocess.run(
            list(map(str, command)), cwd=cwd or self.root, env=env or self.env,
            input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def git(self, *arguments, cwd=None, success=True, input_data=None):
        return self.checked([GIT, "-C", cwd or self.project, *arguments],
                            cwd=cwd or self.project, success=success, input_data=input_data)

    def remote_oid(self):
        return self.git("rev-parse", "refs/heads/gh-pages", cwd=self.remote).stdout.strip()

    def remote_files(self):
        return set(self.git("ls-tree", "-r", "--name-only", "refs/heads/gh-pages", cwd=self.remote).stdout.splitlines())

    def worktree_state(self):
        files = {}
        for path in self.project.rglob("*"):
            relative = path.relative_to(self.project)
            if relative.parts[0] == ".git" or not path.is_file():
                continue
            files[relative.as_posix()] = path.read_bytes()
        return {
            "files": files,
            "index": (self.project / ".git" / "index").read_bytes(),
            "head": (self.project / ".git" / "HEAD").read_bytes(),
            "refs": self.git("show-ref").stdout,
            "worktrees": self.git("worktree", "list", "--porcelain").stdout,
        }

    def launch(self, *arguments, success=True, environment=None, wrapped=False):
        before = self.worktree_state()
        command = (["bash", str(self.project / "deploy.sh")] if wrapped else
                   [sys.executable, "-I", str(self.project / "scripts" / "deploy.py")])
        result = self.checked(command + list(map(str, arguments)), cwd=self.root,
                              env={**self.env, **(environment or {})}, input_data="yes\n", success=False)
        after = self.worktree_state()
        self.assertEqual(after, before, "Deployment changed development files, index, HEAD, refs, or unrelated worktrees")
        self.assertEqual(list(self.scratch.iterdir()), [], "Deployment left temporary resources behind")
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def git_guard(self, failing=None, *, advance_before_push=None, advance_after_commit=None, log=None):
        """Intercept only child Git commands; delegate to the real local Git."""
        directory = self.root / "git-guard"
        directory.mkdir()
        logfile = log or self.root / "git-commands.log"
        body = ["#!/bin/sh", f"printf '%s\\n' \"$*\" >> {shlex.quote(str(logfile))}"]
        if failing == "network":
            body += [
                "for argument in \"$@\"; do",
                "  case \"$argument\" in fetch|ls-remote|push|commit)",
                "    printf '%s\\n' 'unexpected online or write command' >&2; exit 89 ;;",
                "  esac", "done",
            ]
        elif failing:
            body += [
                "for argument in \"$@\"; do",
                f"  if [ \"$argument\" = {shlex.quote(failing)} ]; then",
                f"    printf '%s\\n' 'injected {failing} failure' >&2; exit 87;",
                "  fi", "done",
            ]
        if advance_before_push:
            old, new = advance_before_push
            body += [
                "for argument in \"$@\"; do",
                "  if [ \"$argument\" = push ]; then",
                f"    {shlex.quote(GIT)} --git-dir={shlex.quote(str(self.remote))} update-ref refs/heads/gh-pages {new} {old} || exit 88",
                "  fi", "done",
            ]
        if advance_after_commit:
            old, new = advance_after_commit
            body += [
                "for argument in \"$@\"; do",
                "  if [ \"$argument\" = commit ]; then",
                f"    {shlex.quote(GIT)} \"$@\" || exit $?",
                f"    {shlex.quote(GIT)} --git-dir={shlex.quote(str(self.remote))} update-ref refs/heads/gh-pages {new} {old} || exit 88",
                "    exit 0", "  fi", "done",
            ]
        body.append(f"exec {shlex.quote(GIT)} \"$@\"")
        path = directory / "git"
        path.write_text("\n".join(body) + "\n")
        path.chmod(0o755)
        return {"PATH": str(directory) + os.pathsep + self.env["PATH"]}, logfile

    def new_remote_commit(self):
        tree = self.git("rev-parse", f"{self.baseline}^{{tree}}", cwd=self.remote).stdout.strip()
        return self.git("-c", "user.name=Concurrent Test", "-c", "user.email=concurrent@example.invalid",
                        "commit-tree", tree, "-p", self.baseline, cwd=self.remote,
                        input_data="Concurrent publishing fixture\n").stdout.strip()

    def prepare_clean_baseline(self):
        self.git("worktree", "add", "--detach", str(self.seed), self.baseline)
        self.git("rm", "-r", "--", ".claude", "generate.sh", "obsolete.html", ".gitattributes", cwd=self.seed)
        self.git("commit", "-m", "Clean published baseline", cwd=self.seed)
        previous = self.baseline
        self.baseline = self.git("rev-parse", "HEAD", cwd=self.seed).stdout.strip()
        self.git("worktree", "remove", str(self.seed))
        self.git("update-ref", "refs/heads/gh-pages", self.baseline, previous)
        self.git("push", "origin", "refs/heads/gh-pages:refs/heads/gh-pages")

    def test_default_dry_run_is_offline_and_does_not_touch_dirty_worktrees(self):
        (self.project / "development.txt").write_text("staged local edits\n")
        self.git("add", "development.txt")
        (self.project / "development.txt").write_text("unstaged local edits\n")
        (self.project / "private.local").write_text("do not publish\n")
        other = self.root / "other-worktree"
        self.git("worktree", "add", "--detach", str(other), "HEAD")
        sentinel = other / "owned-by-user.txt"
        sentinel.write_text("untouched\n")
        environment, log = self.git_guard("network")
        result = self.launch(environment=environment)
        self.assertIn("dry-run", result.stdout)
        self.assertIn("D\t.claude/settings.local.json", result.stdout)
        self.assertIn("D\tgenerate.sh", result.stdout)
        self.assertIn("D\t.gitattributes", result.stdout)
        self.assertIn("D\tobsolete.html", result.stdout)
        self.assertNotIn("M\tCNAME", result.stdout)
        self.assertEqual(self.remote_oid(), self.baseline)
        self.assertEqual(sentinel.read_text(), "untouched\n")
        self.assertNotIn(" ls-remote ", log.read_text())

    def test_shell_wrapper_uses_project_paths_from_other_cwd(self):
        result = self.launch("--dry-run", wrapped=True)
        self.assertIn(str(self.output), result.stdout)
        self.assertIn("dry-run 完成", result.stdout)

    def test_explicit_output_path(self):
        alternative = self.root / "separate-output"
        shutil.copytree(self.output, alternative)
        result = self.launch("--repo", alternative)
        self.assertIn(str(alternative), result.stdout)

    def test_publish_explicit_yes_pushes_only_recursive_artifacts(self):
        result = self.launch("--publish", "--yes")
        self.assertIn("已推送发布提交", result.stdout)
        self.assertNotEqual(self.remote_oid(), self.baseline)
        self.assertEqual(self.git("rev-parse", "refs/heads/gh-pages^", cwd=self.remote).stdout.strip(), self.baseline)
        expected = {path.relative_to(self.output).as_posix() for path in self.output.rglob("*") if path.is_file()}
        self.assertEqual(self.remote_files(), expected | {"CNAME"})
        self.assertIn("debs/archive/rootless/com.example.publish-test_1.0-1_iphoneos-arm64.deb", self.remote_files())
        for filename in expected:
            remote_content = subprocess.run(
                [GIT, "-C", str(self.remote), "show", f"refs/heads/gh-pages:{filename}"],
                cwd=self.root, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(remote_content.returncode, 0, remote_content.stderr)
            self.assertEqual(remote_content.stdout, (self.output / filename).read_bytes(), filename)
        self.assertEqual(self.git("show", "refs/heads/gh-pages:CNAME", cwd=self.remote).stdout, "packages.example.invalid\n")

    def test_no_changes_is_distinct_and_stays_offline_even_in_publish_mode(self):
        self.prepare_clean_baseline()
        environment, _ = self.git_guard("network")
        result = self.launch("--publish", "--yes", environment=environment)
        self.assertIn("无更改", result.stdout)
        self.assertNotIn("已推送", result.stdout)
        self.assertEqual(self.remote_oid(), self.baseline)

    def test_publish_without_yes_cannot_use_piped_confirmation(self):
        environment, _ = self.git_guard("network")
        result = self.launch("--publish", environment=environment, success=False)
        self.assertIn("非交互环境", result.stderr)
        self.assertEqual(self.remote_oid(), self.baseline)

    def test_yes_without_publish_is_rejected(self):
        result = self.launch("--yes", success=False)
        self.assertIn("--yes 只能与 --publish", result.stderr)

    def test_fallback_to_remote_tracking_baseline_without_network(self):
        self.git("branch", "-D", "gh-pages")
        environment, _ = self.git_guard("network")
        result = self.launch(environment=environment)
        self.assertIn("基线: refs/remotes/origin/gh-pages", result.stdout)

    def test_explicit_baseline_is_used(self):
        result = self.launch("--baseline-ref", "refs/remotes/origin/gh-pages")
        self.assertIn("基线: refs/remotes/origin/gh-pages", result.stdout)

    def test_missing_baseline_fails_instead_of_creating_branch(self):
        self.git("branch", "-D", "gh-pages")
        self.git("update-ref", "-d", "refs/remotes/origin/gh-pages")
        result = self.launch(success=False)
        self.assertIn("找不到已有 gh-pages 发布基线", result.stderr)

    def test_missing_baseline_packages_cannot_skip_version_protection(self):
        self.git("branch", "-f", "gh-pages", "main")
        result = self.launch(success=False)
        self.assertIn("缺少 Packages", result.stderr)
        self.assertIn("不能跳过同版本覆盖校验", result.stderr)

    def test_missing_compressed_index_is_a_validation_error(self):
        (self.output / "Packages.xz").unlink()
        result = self.launch(success=False)
        self.assertIn("缺少发布产物: Packages.xz", result.stderr)

    def test_invalid_snapshot_never_contacts_remote(self):
        (self.output / "Packages.gz").write_bytes(b"invalid gzip")
        environment, _ = self.git_guard("network")
        result = self.launch("--publish", "--yes", success=False, environment=environment)
        self.assertIn("Packages.gz", result.stderr)
        self.assertEqual(self.remote_oid(), self.baseline)

    def test_extra_output_tool_settings_are_rejected(self):
        (self.output / ".zcode").mkdir()
        (self.output / ".zcode" / "settings.json").write_text("{}\n")
        result = self.launch(success=False)
        self.assertIn("非发布产物", result.stderr)
        self.assertIn(".zcode", result.stderr)

    def test_symlinks_are_rejected(self):
        target = self.output / "Packages.gz"
        content = self.root / "saved.gz"
        target.rename(content)
        target.symlink_to(content)
        result = self.launch(success=False)
        self.assertIn("符号链接", result.stderr)

    def test_nested_deb_symlink_is_rejected(self):
        (self.output / "debs" / "external").symlink_to(self.fixture_output / "debs", target_is_directory=True)
        result = self.launch(success=False)
        self.assertIn("符号链接", result.stderr)

    def test_existing_cname_is_allowed_but_domain_change_is_not(self):
        (self.output / "CNAME").write_text("packages.example.invalid\n")
        self.launch()
        (self.output / "CNAME").write_text("different.example.invalid\n")
        result = self.launch(success=False)
        self.assertIn("不更改域名", result.stderr)

    def test_same_version_modified_bytes_are_rejected_against_git_baseline(self):
        self.git("worktree", "add", "--detach", str(self.seed), self.baseline)
        packages = self.seed / "Packages"
        lines = packages.read_text().splitlines(keepends=True)
        packages.write_text("".join("SHA256: " + "0" * 64 + "\n" if line.startswith("SHA256: ") else line for line in lines))
        self.git("add", "Packages", cwd=self.seed)
        self.git("commit", "-m", "Simulate different published package bytes", cwd=self.seed)
        changed = self.git("rev-parse", "HEAD", cwd=self.seed).stdout.strip()
        self.git("worktree", "remove", str(self.seed))
        self.git("update-ref", "refs/heads/gh-pages", changed, self.baseline)
        result = self.launch(success=False)
        self.assertIn("禁止覆盖已发布的同版本同架构包", result.stderr)

    def test_remote_branch_must_already_exist(self):
        self.git("update-ref", "-d", "refs/heads/gh-pages", cwd=self.remote)
        result = self.launch("--publish", "--yes", success=False)
        self.assertIn("只允许更新已有发布分支", result.stderr)
        self.assertNotEqual(self.git("show-ref", "--verify", "--quiet", "refs/heads/gh-pages", cwd=self.remote, success=False).returncode, 0)

    def test_remote_advance_requires_explicit_fresh_preview(self):
        advanced = self.new_remote_commit()
        self.git("update-ref", "refs/heads/gh-pages", advanced, self.baseline, cwd=self.remote)
        result = self.launch("--publish", "--yes", success=False)
        self.assertIn("远端 gh-pages 已变化", result.stderr)
        self.assertIn("--baseline-ref refs/remotes/origin/gh-pages", result.stderr)
        self.assertEqual(self.remote_oid(), advanced)

    def test_remote_change_after_commit_is_detected_before_push(self):
        advanced = self.new_remote_commit()
        environment, log = self.git_guard(advance_after_commit=(self.baseline, advanced))
        result = self.launch("--publish", "--yes", environment=environment, success=False)
        self.assertIn("远端 gh-pages 已变化", result.stderr)
        self.assertNotIn(" push ", log.read_text())
        self.assertEqual(self.remote_oid(), advanced)

    def test_non_fast_forward_race_is_rejected_without_force(self):
        advanced = self.new_remote_commit()
        environment, log = self.git_guard(advance_before_push=(self.baseline, advanced))
        result = self.launch("--publish", "--yes", environment=environment, success=False)
        self.assertIn("推送失败", result.stderr)
        self.assertNotIn("已推送发布提交", result.stdout)
        commands = log.read_text().splitlines()
        pushes = [line for line in commands if " push " in line]
        self.assertEqual(len(pushes), 1)
        self.assertNotIn("--force", pushes[0])
        self.assertNotIn("+HEAD", pushes[0])
        self.assertEqual(self.remote_oid(), advanced)

    def test_commit_error_is_not_reported_as_no_change(self):
        environment, _ = self.git_guard("commit")
        result = self.launch("--publish", "--yes", environment=environment, success=False)
        self.assertIn("创建发布提交失败", result.stderr)
        self.assertIn("injected commit failure", result.stderr)
        self.assertNotIn("无更改", result.stdout)
        self.assertEqual(self.remote_oid(), self.baseline)

    def test_push_error_is_not_reported_as_success(self):
        environment, _ = self.git_guard("push")
        result = self.launch("--publish", "--yes", environment=environment, success=False)
        self.assertIn("推送失败", result.stderr)
        self.assertIn("injected push failure", result.stderr)
        self.assertNotIn("已推送发布提交", result.stdout)
        self.assertEqual(self.remote_oid(), self.baseline)

    def test_production_hooks_are_not_run_from_temporary_worktree(self):
        hooks = self.root / "hooks"
        hooks.mkdir()
        marker = self.root / "hook-ran"
        for name in ("post-checkout", "pre-commit", "pre-push"):
            hook = hooks / name
            hook.write_text(f"#!/bin/sh\nprintf hook > {shlex.quote(str(marker))}\nexit 83\n")
            hook.chmod(0o755)
        self.git("config", "core.hooksPath", str(hooks))
        self.launch("--publish", "--yes")
        self.assertFalse(marker.exists())

    def test_local_git_clean_filters_are_not_executed(self):
        marker = self.root / "filter-ran"
        command = f"printf filter > {shlex.quote(str(marker))}; exit 82"
        self.git("config", "filter.forbidden.clean", command)
        self.git("config", "filter.forbidden.required", "true")
        (self.project / ".git" / "info" / "attributes").write_text("* filter=forbidden\n")
        self.launch()
        self.assertFalse(marker.exists())

    def test_git_index_override_is_refused_before_touching_anything(self):
        alien_index = self.root / "unrelated-index"
        alien_index.write_bytes(b"leave me alone")
        result = self.launch(environment={"GIT_INDEX_FILE": str(alien_index)}, success=False)
        self.assertIn("GIT_INDEX_FILE", result.stderr)
        self.assertEqual(alien_index.read_bytes(), b"leave me alone")


if __name__ == "__main__":
    unittest.main()
