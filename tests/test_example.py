"""Example-only tests; run with python3 -I tests/test_example.py."""
import argparse
from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_example", ROOT / "scripts/build_example.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


def payload(*names):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name in names:
            info = tarfile.TarInfo(name)
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
    return stream.getvalue()


class ExampleTests(unittest.TestCase):
    def setUp(self):
        self.control = (ROOT / "examples/HelloTweak/control").read_text(encoding="utf-8")

    def test_cli_defaults_to_both(self):
        with patch.dict("os.environ", {}, clear=True):
            args = build.parser().parse_args([])
        self.assertEqual(args.scheme, "both")
        self.assertIsNone(args.package_version)

    def test_help_without_theos_or_build_output(self):
        result = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/build_example.py"), "--help"], env={"THEOS": "/does/not/exist"}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--scheme {both,rootful,rootless}", result.stdout)
        self.assertIn("not deployment target", " ".join(result.stdout.split()))
        self.assertIn("FINALPACKAGE=1", result.stdout)

    def test_bad_scheme_is_rejected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
            build.parser().parse_args(["--scheme", "other"])
        self.assertEqual(failure.exception.code, 2)

    def test_cpu_and_debian_architectures_are_distinct(self):
        self.assertEqual(build.archs("arm64,arm64e"), "arm64 arm64e")
        for invalid in ("iphoneos-arm", "iphoneos-arm64", "arm64 arm64", "x86_64", ""):
            with self.subTest(invalid=invalid), self.assertRaises(argparse.ArgumentTypeError):
                build.archs(invalid)

    def test_version_is_reusable_without_scheme_suffix(self):
        for version in ("1.0.0-1", "2.0~beta1", "1:2.0-3"):
            self.assertEqual(build.package_version(version), version)
        for invalid in ("$(shell touch /tmp/unwanted)", "v1", "1 2", "1/2", "1\n2"):
            with self.subTest(invalid=invalid), self.assertRaises(argparse.ArgumentTypeError):
                build.package_version(invalid)

    def test_control_tracks_scheme_and_minimum_without_source_mutation(self):
        for scheme, minimum, architecture in (("rootful", "12.0", "iphoneos-arm"), ("rootless", "15.0", "iphoneos-arm64")):
            fields = build.read_control(build.staged_control(self.control, scheme, "1.2.3-4", minimum))
            self.assertEqual(fields["version"], "1.2.3-4")
            self.assertEqual(fields["architecture"], architecture)
            self.assertEqual(fields["depends"], f"mobilesubstrate (>= 0.9.5000), firmware (>= {minimum})")
            self.assertNotIn("ellekit", fields["depends"])
        self.assertEqual((ROOT / "examples/HelloTweak/control").read_text(encoding="utf-8"), self.control)

    def test_explicit_invalid_theos_never_falls_back(self):
        with self.assertRaisesRegex(build.BuildError, "Invalid explicit THEOS"):
            build.discover_theos({"THEOS": "/definitely/no/theos"})
        with self.assertRaisesRegex(build.BuildError, "empty"):
            build.discover_theos({"THEOS": ""})

    def test_theos_discovery_validates_candidates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid = root / "valid"
            for name in build.REQUIRED_THEOS_FILES:
                path = valid / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            self.assertEqual(build.discover_theos({}, [root / "missing", valid]), valid.resolve())
            self.assertEqual(build.discover_theos({"THEOS": str(valid)}), valid.resolve())

    def test_new_runs_are_isolated_and_symlinks_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = build.new_run_directory(root)
            marker = first / "keep"
            marker.touch()
            second = build.new_run_directory(root)
            self.assertNotEqual(first, second)
            self.assertTrue(marker.exists())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".build").symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(build.BuildError, "symlinked"):
                build.new_run_directory(root)

    @unittest.skipUnless(shutil.which("make"), "make is not available")
    def test_mk_defaults_match_source_control(self):
        with patch.dict("os.environ", {}, clear=True):
            args = build.parser().parse_args([])
        configs = {scheme: build.build_config(shutil.which("make"), scheme, args, {}) for scheme in ("rootful", "rootless")}
        self.assertEqual(configs["rootful"]["ARCHS"], "arm64")
        self.assertEqual(configs["rootless"]["ARCHS"], "arm64 arm64e")
        self.assertEqual(configs["rootless"]["DEPLOYMENT_TARGET"], "15.0")
        self.assertEqual(build.read_control(self.control)["depends"], build.dependencies(configs["rootful"]["DEPLOYMENT_TARGET"]))

    @unittest.skipUnless(shutil.which("make"), "make is not available")
    def test_arm64e_legacy_abi_is_not_claimed(self):
        args = build.parser().parse_args(["--rootful-archs", "arm64 arm64e"])
        with self.assertRaisesRegex(build.BuildError, "Modern arm64e ABI"):
            build.build_config(shutil.which("make"), "rootful", args, {})

    def test_make_arguments_are_release_and_isolated(self):
        config = {"ARCHS": "arm64", "DEPLOYMENT_TARGET": "12.0", "SDK_VERSION": "latest"}
        for scheme, value in (("rootful", ""), ("rootless", "rootless")):
            source = Path(f"/repo/.build/examples/new/{scheme}/source")
            command = build.make_command("make", Path("/opt/theos"), source, scheme, config, "1.0.0-1")
            self.assertIn(f"THEOS_PACKAGE_SCHEME={value}", command)
            self.assertIn("FINALPACKAGE=1", command)
            self.assertIn("TARGET=iphone:clang:latest:12.0", command)
            for name, suffix in (("_THEOS_LOCAL_DATA_DIR", ".theos"), ("THEOS_STAGING_DIR", "staging"), ("THEOS_PACKAGE_DIR", "packages")):
                self.assertIn(f"{name}={source.parent / suffix}", command)
            self.assertFalse({"clean", "install", "do"}.intersection(command))

    def test_payload_prefixes_are_checked_in_memory(self):
        for scheme, prefix in (("rootful", ""), ("rootless", "var/jb/")):
            data = payload(*(f"./{prefix}Library/MobileSubstrate/DynamicLibraries/HelloTweak.{ext}" for ext in ("dylib", "plist")))
            build.verify_payload(data, scheme)
            with self.assertRaises(build.BuildError):
                build.verify_payload(data, "rootless" if scheme == "rootful" else "rootful")
        with self.assertRaisesRegex(build.BuildError, "Unsafe"):
            build.verify_payload(payload("../escape"), "rootful")

    def test_package_identity_comes_from_control_not_filename(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "packages").mkdir()
            package = directory / "packages/misleading-name.deb"
            package.touch()
            metadata = build.staged_control(self.control, "rootless", "1.0.0-1", "15.0")
            data = payload(*(f"./var/jb/Library/MobileSubstrate/DynamicLibraries/HelloTweak.{ext}" for ext in ("dylib", "plist")))
            expected = build.read_control(metadata)
            with patch.object(build, "checked_output", side_effect=[metadata.encode(), data]) as output:
                self.assertEqual(build.find_package(directory, "dpkg-deb", "rootless", expected, {}), package)
                self.assertEqual(output.call_args_list[0].args[0][1], "--field")
                self.assertEqual(output.call_args_list[1].args[0][1], "--fsys-tarfile")

    def test_hook_is_guarded_and_no_passthrough_hook_remains(self):
        source = (ROOT / "examples/HelloTweak/Tweak.x").read_text(encoding="utf-8")
        self.assertNotIn("setDate:", source)
        self.assertNotIn("SBStatusBarContentView", source)
        self.assertEqual(source.count("%init("), 1)
        guard = source.index("if (provider != Nil && class_getInstanceMethod(provider, @selector(timeString)) != NULL)")
        self.assertLess(guard, source.index("%init(HelloTweakHooks"))
        self.assertIn("objc_getClass(\"SBStatusBarStateProvider\")", source)
        self.assertIn("stringByAppendingString:@\" \U0001f525\"", source)
        self.assertIn("NSString *original = %orig;", source)


if __name__ == "__main__":
    unittest.main()
