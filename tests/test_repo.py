import bz2
import gzip
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repo.py"
spec = importlib.util.spec_from_file_location("repo", SCRIPT)
repo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repo)
TOOLS_AVAILABLE = all(shutil.which(tool) for tool in ("dpkg", "dpkg-deb", "dpkg-scanpackages"))


@unittest.skipUnless(TOOLS_AVAILABLE, "需要 dpkg / dpkg-deb / dpkg-scanpackages")
class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mytweak-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.debs = self.root / "input"
        self.debs.mkdir()
        self.output = self.root / "output"
        self.config = self.root / "repo.json"
        shutil.copyfile(ROOT / "repo.json", self.config)
        self.counter = 0

    def package(self, name="com.example.test", version="1.0-1", architecture="iphoneos-arm",
                folder="", body="test payload\n", extra="", filename=None):
        self.counter += 1
        source = self.root / f"fixture-{self.counter}"
        (source / "DEBIAN").mkdir(parents=True)
        control = (
            f"Package: {name}\nVersion: {version}\nArchitecture: {architecture}\n"
            "Maintainer: Fixture <fixture@example.invalid>\n"
            "Description: Test package\n continuation text\n .\n final paragraph\n"
            "Section: Tweaks\nDepends: mobilesubstrate (>= 0.9.5000)\n" + extra
        )
        (source / "DEBIAN" / "control").write_text(control, encoding="utf-8")
        destination = source / "usr" / "share" / name
        destination.mkdir(parents=True)
        (destination / "fixture.txt").write_text(body, encoding="utf-8")
        path = self.debs / folder / (filename or f"{name}_{version}_{architecture}.deb")
        path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["dpkg-deb", "--build", "--root-owner-group", "-Zgzip", str(source), str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return path

    def cli(self, *arguments, success=True, env=None):
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), *map(str, arguments)],
            cwd=self.root, env={**os.environ, **(env or {})}, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def build(self, success=True, *arguments, env=None):
        return self.cli(
            "build", "--debs", self.debs, "--output", self.output, "--config", self.config,
            *arguments, success=success, env=env,
        )

    def validate(self, success=True, *arguments):
        return self.cli("validate", "--repo", self.output, *arguments, success=success)

    def snapshot(self, directory):
        return {
            path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob("*") if path.is_file()
        }

    def test_single_architecture_and_compressed_indexes(self):
        self.package()
        self.build()
        self.validate()
        release = (self.output / "Release").read_text()
        self.assertIn("Architectures: iphoneos-arm\n", release)
        self.assertNotIn("\n\n", release)
        raw = (self.output / "Packages").read_bytes()
        for suffix, decompress in (("gz", gzip.decompress), ("bz2", bz2.decompress), ("xz", lzma.decompress)):
            self.assertEqual(decompress((self.output / f"Packages.{suffix}").read_bytes()), raw)
        self.assertIn(b"Depends: mobilesubstrate (>= 0.9.5000)", raw)
        self.assertIn(b" continuation text\n .\n final paragraph", raw)

    def test_both_architectures_versions_and_nested_files(self):
        self.package(folder="rootful")
        self.package(architecture="iphoneos-arm64", folder="rootless")
        self.package(version="1.1-1", folder="archive/rootful")
        self.build()
        self.validate()
        records = repo.read_stanzas(self.output / "Packages")
        self.assertEqual(len(records), 3)
        self.assertIn("Architectures: iphoneos-arm iphoneos-arm64\n", (self.output / "Release").read_text())
        self.assertTrue((self.output / "debs/rootless/com.example.test_1.0-1_iphoneos-arm64.deb").is_file())

    def test_architecture_comes_from_control_not_filename(self):
        self.package(architecture="iphoneos-arm64", filename="misleading_iphoneos-arm.deb")
        self.build()
        self.assertIn("Architectures: iphoneos-arm64\n", (self.output / "Release").read_text())

    def test_all_architecture_resource_package(self):
        self.package(architecture="all")
        self.build()
        self.validate()
        self.assertIn("Architectures: all\n", (self.output / "Release").read_text())

    def test_empty_input_rejected(self):
        self.assertIn("没有找到 deb", self.build(success=False).stderr)
        self.assertFalse(self.output.exists())

    def test_bad_archive_rejected(self):
        (self.debs / "broken.deb").write_bytes(b"not a package")
        self.build(success=False)
        self.assertFalse(self.output.exists())

    def test_truncated_data_archive_rejected(self):
        path = self.package()
        data = path.read_bytes()
        path.write_bytes(data[:-50])
        self.build(success=False)

    def test_duplicate_identity_rejected(self):
        original = self.package()
        shutil.copyfile(original, self.debs / "another.deb")
        self.assertIn("重复的", self.build(success=False).stderr)

    def test_unsupported_architecture_rejected(self):
        self.package(architecture="amd64")
        self.assertIn("不支持的架构", self.build(success=False).stderr)

    def test_control_index_fields_rejected(self):
        self.package(extra="Filename: debs/not-real.deb\n")
        self.assertIn("索引字段", self.build(success=False).stderr)

    def test_unsafe_input_filename_rejected(self):
        original = self.package()
        original.rename(self.debs / "bad file.deb")
        self.assertIn("路径", self.build(success=False).stderr)

    def test_symlink_input_file_rejected(self):
        path = self.package()
        (self.debs / "alias.deb").symlink_to(path)
        self.assertIn("符号链接", self.build(success=False).stderr)

    def test_symlink_input_root_rejected(self):
        self.package()
        alias = self.root / "alias"
        alias.symlink_to(self.debs, target_is_directory=True)
        result = self.cli("build", "--debs", alias, "--output", self.output, success=False)
        self.assertIn("符号链接", result.stderr)

    def test_symlink_input_subdirectory_rejected(self):
        self.package()
        (self.debs / "external").symlink_to(self.root, target_is_directory=True)
        self.assertIn("符号链接", self.build(success=False).stderr)

    def test_output_cannot_overlap_input(self):
        self.package()
        for output in (self.debs, self.debs / "generated", self.root, ROOT):
            with self.subTest(output=output):
                result = self.cli("build", "--debs", self.debs, "--output", output, success=False)
                self.assertIn("输出", result.stderr)

    def test_existing_unrelated_output_not_overwritten(self):
        self.package()
        self.output.mkdir()
        (self.output / "keep.txt").write_text("user data")
        self.build(success=False)
        self.assertEqual((self.output / "keep.txt").read_text(), "user data")

    def test_failed_build_preserves_previous_valid_output(self):
        self.package()
        self.build()
        before = self.snapshot(self.output)
        (self.debs / "broken.deb").write_bytes(b"bad archive")
        self.build(success=False)
        self.assertEqual(self.snapshot(self.output), before)
        self.assertFalse((self.output.parent / ".output.lock").exists())

    def test_rebuild_is_reproducible(self):
        self.package()
        self.build(env={"SOURCE_DATE_EPOCH": "1700000000"})
        before = self.snapshot(self.output)
        self.build(env={"SOURCE_DATE_EPOCH": "1700000000"})
        self.assertEqual(self.snapshot(self.output), before)

    def test_invalid_epoch_rejected(self):
        self.package()
        for value in ("invalid", "-1", "9999999999999999999999999"):
            with self.subTest(value=value):
                self.build(success=False, env={"SOURCE_DATE_EPOCH": value})

    def test_output_lock_prevents_concurrent_build(self):
        self.package()
        lock = self.output.parent / ".output.lock"
        lock.write_text("another process")
        self.assertIn("锁", self.build(success=False).stderr)
        self.assertEqual(lock.read_text(), "another process")
        self.assertFalse(self.output.exists())

    def test_symlink_output_rejected(self):
        self.package()
        target = self.root / "user-folder"
        target.mkdir()
        (target / "keep").write_text("data")
        self.output.symlink_to(target, target_is_directory=True)
        self.assertIn("符号链接", self.build(success=False).stderr)
        self.assertEqual((target / "keep").read_text(), "data")

    def test_missing_indexed_package_rejected(self):
        first = self.package()
        self.package(name="com.example.other")
        self.build()
        (self.output / "debs" / first.name).unlink()
        self.assertIn("不存在", self.validate(success=False).stderr)

    def test_unindexed_package_rejected(self):
        self.package()
        self.build()
        other = self.package(name="com.example.other")
        shutil.copy2(other, self.output / "debs" / other.name)
        self.assertIn("完整收录", self.validate(success=False).stderr)

    def test_modified_package_rejected(self):
        path = self.package()
        self.build()
        destination = self.output / "debs" / path.name
        destination.write_bytes(destination.read_bytes() + b"changed")
        self.validate(success=False)

    def test_index_hash_tampering_rejected(self):
        self.package()
        self.build()
        path = self.output / "Packages"
        path.write_text(path.read_text().replace("SHA256: ", "SHA256: 0", 1))
        self.assertIn("sha256", self.validate(success=False).stderr)

    def test_index_path_traversal_rejected(self):
        self.package()
        self.build()
        path = self.output / "Packages"
        path.write_text(path.read_text().replace("Filename: debs/", "Filename: ../debs/", 1))
        self.assertIn("路径", self.validate(success=False).stderr)

    def test_compressed_index_tampering_rejected(self):
        self.package()
        self.build()
        (self.output / "Packages.gz").write_bytes(gzip.compress(b"different"))
        self.assertIn("解压后", self.validate(success=False).stderr)

    def test_release_hash_tampering_rejected(self):
        self.package()
        self.build()
        path = self.output / "Release"
        path.write_text(path.read_text().replace(" Packages.gz\n", " Packages.gz-extra\n", 1))
        self.assertIn("Release", self.validate(success=False).stderr)

    def test_release_architectures_must_match_actual_packages(self):
        self.package()
        self.build()
        path = self.output / "Release"
        path.write_text(path.read_text().replace("Architectures: iphoneos-arm", "Architectures: iphoneos-arm64"))
        self.assertIn("Architectures", self.validate(success=False).stderr)

    def test_release_must_not_contain_separate_stanzas(self):
        self.package()
        self.build()
        path = self.output / "Release"
        path.write_text(path.read_text().replace("MD5Sum:", "\nMD5Sum:", 1))
        self.assertIn("一个连续", self.validate(success=False).stderr)

    def test_release_duplicate_hash_entry_rejected(self):
        self.package()
        self.build()
        path = self.output / "Release"
        text = path.read_text()
        line = next(line for line in text.splitlines() if line.endswith(" Packages"))
        path.write_text(text.replace(line, line + "\n" + line, 1))
        self.assertIn("重复", self.validate(success=False).stderr)

    def test_baseline_accepts_unchanged_package(self):
        self.package()
        self.build()
        self.validate(True, "--baseline", self.output)

    def test_baseline_rejects_same_version_replacement(self):
        path = self.package()
        self.build()
        baseline = self.root / "baseline-Packages"
        shutil.copyfile(self.output / "Packages", baseline)
        before = self.snapshot(self.output)
        self.package(filename=path.name, body="different payload")
        result = self.build(False, "--baseline", baseline)
        self.assertIn("禁止覆盖", result.stderr)
        self.assertEqual(self.snapshot(self.output), before)

    def test_baseline_accepts_new_version_and_second_architecture(self):
        self.package()
        self.build()
        baseline = self.root / "baseline-Packages"
        shutil.copyfile(self.output / "Packages", baseline)
        self.package(version="1.1-1", body="new payload")
        self.package(architecture="iphoneos-arm64")
        self.build(True, "--baseline", baseline)

    def test_invalid_baseline_fails_closed(self):
        self.package()
        self.build()
        baseline = self.root / "baseline"
        for data in ("", "Package: com.example.test\nVersion: 1.0-1\nArchitecture: iphoneos-arm\n"):
            baseline.write_text(data)
            self.validate(False, "--baseline", baseline)
        self.validate(False, "--baseline", self.root / "missing")

    def test_output_whitelist_allows_cname_but_not_scripts(self):
        self.package()
        self.build()
        (self.output / "CNAME").write_text("example.invalid\n")
        self.validate()
        (self.output / "unexpected.py").write_text("raise RuntimeError('not executed')\n")
        self.validate(success=False)

    def test_output_symlink_rejected(self):
        self.package()
        self.build()
        (self.output / "CNAME").symlink_to(self.config)
        self.assertIn("符号链接", self.validate(success=False).stderr)

    def test_homepage_escapes_metadata(self):
        self.package(extra="Name: <script>alert(1)</script>\n")
        self.build()
        text = (self.output / "index.html").read_text()
        self.assertIn("&lt;script&gt;", text)
        self.assertNotIn("<script>", text)

    def test_configuration_rejects_header_and_url_injection(self):
        self.package()
        original = json.loads(self.config.read_text())
        for field, value in (("origin", "evil\nArchitectures: all"), ("url", "javascript:alert(1)")):
            with self.subTest(field=field):
                self.config.write_text(json.dumps({**original, field: value}))
                self.build(success=False)

    def test_equivalent_debian_versions_are_duplicates(self):
        self.package(version="1.0-1")
        self.package(version="1.0-01")
        self.assertIn("Debian 等价版本", self.build(success=False).stderr)

    def test_equivalent_version_cannot_bypass_baseline(self):
        path = self.package(version="1.0-1")
        self.build()
        baseline = self.root / "baseline"
        shutil.copyfile(self.output / "Packages", baseline)
        path.unlink()
        self.package(version="1.0-01", body="changed payload")
        self.assertIn("禁止覆盖", self.build(False, "--baseline", baseline).stderr)

    def test_index_cannot_add_installation_metadata(self):
        self.package()
        self.build()
        path = self.output / "Packages"
        path.write_text(path.read_text().replace("Package:", "Conflicts: dpkg\nPackage:", 1))
        self.assertIn("字段集合", self.validate(success=False).stderr)

    def test_legal_custom_control_fields_and_unicode_separators(self):
        self.package(extra="X_Custom: value\nName: Unicode\u2028line\u2029separator\n")
        self.build()
        self.validate()
        text = (self.output / "Packages").read_text()
        self.assertIn("x_custom: value", text.lower())
        self.assertIn("Unicode\u2028line\u2029separator", text)

    def test_compressed_stream_trailing_garbage_rejected(self):
        self.package()
        self.build()
        for name in ("Packages.gz", "Packages.bz2", "Packages.xz"):
            with self.subTest(name=name):
                path = self.output / name
                original = path.read_bytes()
                path.write_bytes(original + b"GARBAGE")
                self.assertIn("尾数据", self.validate(success=False).stderr)
                path.write_bytes(original)

    def test_interrupt_during_output_swap_preserves_old_output(self):
        self.package()
        self.build()
        before = self.snapshot(self.output)
        original_rename = Path.rename

        def interrupt_staging(path, target):
            if path.name == "repo" and path.parent.name.startswith(".repo-build-"):
                raise KeyboardInterrupt("simulated Ctrl-C")
            return original_rename(path, target)

        with mock.patch.object(Path, "rename", interrupt_staging), self.assertRaises(KeyboardInterrupt):
            repo.build_repo(self.debs, self.output, self.config)
        self.assertEqual(self.snapshot(self.output), before)
        self.assertFalse((self.root / ".output.previous").exists())

    def test_rollback_failure_keeps_backup_for_manual_recovery(self):
        self.package()
        self.build()
        before = self.snapshot(self.output)
        original_rename = Path.rename

        def fail_rename(path, target):
            if path.name == "repo" and path.parent.name.startswith(".repo-build-"):
                raise KeyboardInterrupt("simulated Ctrl-C")
            if path.name == ".output.previous":
                raise OSError("simulated recovery failure")
            return original_rename(path, target)

        with mock.patch.object(Path, "rename", fail_rename), self.assertRaises(OSError):
            repo.build_repo(self.debs, self.output, self.config)
        backup = self.root / ".output.previous"
        self.assertEqual(self.snapshot(backup), before)
        self.assertIn("待恢复", self.build(success=False).stderr)
        self.assertEqual(self.snapshot(backup), before)

    def test_missing_tool_has_actionable_error(self):
        self.package()
        result = self.build(success=False, env={"PATH": str(self.root / "empty-path")})
        self.assertIn("缺少工具", result.stderr)

    def test_shell_entrypoints_work_from_another_directory(self):
        self.package()
        for name in ("generate.sh", "update.sh"):
            result = subprocess.run(
                ["bash", str(ROOT / name), "--debs", str(self.debs), "--output", str(self.output)],
                cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


class ControlParserTests(unittest.TestCase):
    def test_duplicate_fields_are_case_insensitive(self):
        with self.assertRaises(repo.RepoError):
            repo.parse_stanzas("Package: one\nPACKAGE: two\n", "test")

    def test_orphan_continuation_rejected(self):
        with self.assertRaises(repo.RepoError):
            repo.parse_stanzas(" continuation\n", "test")

    def test_safe_filename_rejects_noncanonical_paths(self):
        for name in ("", "/debs/a.deb", "./debs/a.deb", "debs/../a.deb", "debs//a.deb", "debs/a%2fb.deb", "other/a.deb"):
            with self.subTest(name=name), self.assertRaises(repo.RepoError):
                repo.safe_filename(name)


if __name__ == "__main__":
    unittest.main()
