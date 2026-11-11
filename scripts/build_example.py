#!/usr/bin/env python3
"""Build the example in fresh, scheme-specific trees; never install or publish."""
from __future__ import annotations

import argparse
import io
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile


REPO = Path(__file__).resolve().parents[1]
DEBIAN_ARCHS = {"rootful": "iphoneos-arm", "rootless": "iphoneos-arm64"}
MINIMUM_IOS = {"rootful": (12, 0, 0), "rootless": (15, 0, 0)}
REQUIRED_THEOS_FILES = (
    "makefiles/common.mk", "makefiles/tweak.mk", "Prefix.pch",
    "bin/logos.pl", "bin/fakeroot.sh", "vendor/include/substrate.h",
)


class BuildError(Exception):
    pass


def archs(value: str) -> str:
    names = value.replace(",", " ").split()
    if not names or len(set(names)) != len(names) or set(names) - {"arm64", "arm64e"}:
        raise argparse.ArgumentTypeError("CPU slices must be arm64 and/or arm64e, without duplicates (not iphoneos-arm/iphoneos-arm64)")
    return " ".join(names)


def ios_version(value: str) -> str:
    if not re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", value):
        raise argparse.ArgumentTypeError("expected an iOS version such as 12.0 or 15.0")
    return value


def sdk_version(value: str) -> str:
    return value if value == "latest" else ios_version(value)


def package_version(value: str) -> str:
    if not re.fullmatch(r"(?:[0-9]+:)?[0-9][A-Za-z0-9.+~]*(?:-[A-Za-z0-9.+~\-]+)?", value):
        raise argparse.ArgumentTypeError("expected a Debian version such as 1.0.0-1 (no spaces or make expressions)")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Build HelloTweak release packages in a NEW .build/examples/hellotweak-*/<scheme>/ tree. Never cleans existing builds, copies into debs/, installs, or connects to a device.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Defaults come from mk/example.mk:
  rootful:  Mach-O arm64,        iOS >= 12.0; Debian iphoneos-arm
  rootless: Mach-O arm64 arm64e, iOS >= 15.0; Debian iphoneos-arm64
  SDK: latest available to Theos. Both schemes use FINALPACKAGE=1 and one version.

THEOS: use the explicit environment value, otherwise check ~/theos, /opt/theos,
/usr/local/theos and /opt/homebrew/theos. Invalid explicit THEOS is an error.
Requires existing Python 3.9+, make, dpkg-deb and a working Theos toolchain/SDK;
no dependencies are installed. A build failure is returned, not skipped.

Examples:
  ./examples/compile.sh
  THEOS=/opt/theos ./examples/compile.sh --scheme rootless --version 1.0.1-1
  ./examples/compile.sh --sdk 16.5 --rootless-archs 'arm64 arm64e'

Outputs: <run>/<scheme>/{source,.theos,staging,packages,build.log}.
Packages are identified by their control fields, NOT a .rootless. filename.
The script prints the verified deb paths; publishing is a separate operation.
""",
    )
    result.add_argument("--scheme", choices=("both", "rootful", "rootless"), default="both", help="package layout(s), default: both; rootful passes an EMPTY Theos scheme")
    result.add_argument("--version", dest="package_version", type=package_version, default=os.environ.get("PACKAGE_VERSION"), metavar="VERSION", help="same Debian version for both builds; default: PACKAGE_VERSION or source control")
    result.add_argument("--sdk", type=sdk_version, help="Theos iPhoneOS SDK version, e.g. 16.5 or latest (not deployment target)")
    for scheme in DEBIAN_ARCHS:
        result.add_argument(f"--{scheme}-archs", type=archs, metavar="SLICES", help=f"{scheme} Mach-O slices, quoted or comma-separated: arm64, arm64e")
        result.add_argument(f"--{scheme}-min-ios", type=ios_version, metavar="VERSION", help=f"{scheme} deployment target AND firmware dependency; default from mk/example.mk")
    return result


def make_environment() -> dict[str, str]:
    env = dict(os.environ)
    # A surrounding make must not redirect this independent build or load files.
    for key in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "MAKEFILES", "MAKELEVEL"):
        env.pop(key, None)
    return env


def checked_output(command: list[str], *, cwd: Path, env: dict[str, str]) -> bytes:
    completed = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise BuildError(f"{shlex.join(command)} failed ({completed.returncode}): {detail}")
    if completed.stderr:
        print(completed.stderr.decode("utf-8", errors="replace"), end="", file=sys.stderr)
    return completed.stdout


def validate_make_path(path: Path) -> None:
    if any(c.isspace() or c in "$#" for c in str(path)):
        raise BuildError(f"Theos/make paths must not contain whitespace, '$' or '#': {path}")


def discover_theos(env: dict[str, str], candidates=None) -> Path:
    explicit = env.get("THEOS")
    if explicit is not None and not explicit.strip():
        raise BuildError("THEOS is set but empty; unset it to enable automatic discovery")
    paths = [Path(explicit).expanduser()] if explicit is not None else (
        candidates if candidates is not None else [Path.home() / "theos", Path("/opt/theos"), Path("/usr/local/theos"), Path("/opt/homebrew/theos")]
    )
    problems = []
    for path in paths:
        path = path.resolve()
        missing = [name for name in REQUIRED_THEOS_FILES if not (path / name).is_file()]
        if not missing:
            validate_make_path(path)
            return path
        problem = f"{path}: missing {', '.join(missing)}"
        problems.append(problem)
        if explicit is not None:
            raise BuildError(f"Invalid explicit THEOS (no fallback): {problem}")
        if path.exists():
            print(f"Skipping incomplete Theos candidate: {problem}", file=sys.stderr)
    raise BuildError("No valid Theos installation found; set THEOS. Checked:\n" + "\n".join(problems))


def read_control(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    previous = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith((" ", "\t")) and previous:
            fields[previous] += "\n" + line
            continue
        name, separator, value = line.partition(":")
        key = name.lower()
        if not separator or key in fields:
            raise BuildError(f"Invalid or duplicate control field: {line}")
        fields[key] = value.strip()
        previous = key
    for name in ("package", "version", "architecture", "depends"):
        if not fields.get(name):
            raise BuildError(f"Missing control field: {name}")
    return fields


def dependencies(minimum: str) -> str:
    return f"mobilesubstrate (>= 0.9.5000), firmware (>= {minimum})"


def staged_control(original: str, scheme: str, version: str, minimum: str) -> str:
    read_control(original)
    replacements = {"Architecture": DEBIAN_ARCHS[scheme], "Version": version, "Depends": dependencies(minimum)}
    for field, value in replacements.items():
        original = re.sub(rf"^{field}:.*(?:\n[ \t].*)*", lambda _: f"{field}: {value}", original, flags=re.IGNORECASE | re.MULTILINE)
    return original


def build_config(make: str, scheme: str, args: argparse.Namespace, env: dict[str, str]) -> dict[str, str]:
    command = [make, "--no-print-directory", "-s", "-f", str(REPO / "mk/example.mk"), "example-config", f"THEOS_PACKAGE_SCHEME={'rootless' if scheme == 'rootless' else ''}"]
    for variable, value in (
        ("ARCHS", getattr(args, f"{scheme}_archs")),
        ("EXAMPLE_DEPLOYMENT_TARGET", getattr(args, f"{scheme}_min_ios")),
        ("EXAMPLE_SDK_VERSION", args.sdk),
    ):
        if value is not None:
            command.append(f"{variable}={value}")
    text = checked_output(command, cwd=REPO, env=env).decode("utf-8")
    config = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    try:
        config["ARCHS"] = archs(config["ARCHS"])
        config["DEPLOYMENT_TARGET"] = ios_version(config["DEPLOYMENT_TARGET"])
        config["SDK_VERSION"] = sdk_version(config["SDK_VERSION"])
    except (KeyError, argparse.ArgumentTypeError) as error:
        raise BuildError(f"Invalid {scheme} mk/example.mk configuration: {error}") from error
    numbers = [int(part) for part in config["DEPLOYMENT_TARGET"].split(".")]
    minimum = tuple((numbers + [0, 0])[:3])
    if minimum < MINIMUM_IOS[scheme]:
        raise BuildError(f"{scheme} minimum iOS must be >= {MINIMUM_IOS[scheme][0]}.0")
    if "arm64e" in config["ARCHS"].split() and minimum < (14, 0, 0):
        raise BuildError("Modern arm64e ABI requires iOS >= 14.0; keep rootful arm64 or raise --rootful-min-ios. Legacy iOS 12/13 arm64e needs a separately validated toolchain.")
    return config


def new_run_directory(repo: Path) -> Path:
    for directory in (repo / ".build", repo / ".build/examples"):
        if directory.is_symlink():
            raise BuildError(f"Refusing symlinked build directory: {directory}")
        directory.mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="hellotweak-", dir=repo / ".build/examples"))


def stage_source(directory: Path, scheme: str, version: str, minimum: str, original: str) -> Path:
    source = directory / "source"
    source.mkdir(parents=True, exist_ok=False)
    for name in ("Makefile", "Tweak.x", "HelloTweak.plist"):
        shutil.copy2(REPO / "examples/HelloTweak" / name, source / name)
    shutil.copy2(REPO / "mk/example.mk", source / "example.mk")
    (source / "control").write_text(staged_control(original, scheme, version, minimum), encoding="utf-8")
    return source


def make_command(make: str, theos: Path, source: Path, scheme: str, config: dict[str, str], version: str) -> list[str]:
    directory = source.parent
    command = [make, "--no-print-directory", "-C", str(source)]
    values = {
        "THEOS": theos, "EXAMPLE_STAGED_BUILD": "1",
        "THEOS_PACKAGE_SCHEME": "rootless" if scheme == "rootless" else "",
        "THEOS_PROJECT_DIR": source, "THEOS_BUILD_DIR": directory,
        "_THEOS_LOCAL_DATA_DIR": directory / ".theos",
        "THEOS_STAGING_DIR": directory / "staging", "THEOS_PACKAGE_DIR": directory / "packages",
        "THEOS_LAYOUT_DIR": source / "layout",
        "ARCHS": config["ARCHS"], "EXAMPLE_DEPLOYMENT_TARGET": config["DEPLOYMENT_TARGET"],
        "EXAMPLE_SDK_VERSION": config["SDK_VERSION"],
        "target": "", "TARGET": f"iphone:clang:{config['SDK_VERSION']}:{config['DEPLOYMENT_TARGET']}",
        "PACKAGE_VERSION": version, "FINALPACKAGE": "1", "DEBUG": "0", "debug": "0",
        "PACKAGE_BUILDNAME": "", "COLOR": "0",
    }
    if scheme == "rootful":
        values["THEOS_PACKAGE_INSTALL_PREFIX"] = ""
    return command + [f"{key}={value}" for key, value in values.items()]


def run_logged(command: list[str], directory: Path, env: dict[str, str]) -> None:
    with (directory / "build.log").open("a", encoding="utf-8") as log:
        heading = "$ " + shlex.join(command) + "\n"
        print(heading, end="", flush=True)
        log.write(heading)
        with subprocess.Popen(command, cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace") as process:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
            result = process.wait()
        if result:
            raise BuildError(f"Build command failed ({result}); preserved log and intermediate files in {directory}")


def verify_payload(data: bytes, scheme: str) -> None:
    prefix = "var/jb/" if scheme == "rootless" else ""
    expected = {prefix + f"Library/MobileSubstrate/DynamicLibraries/HelloTweak.{suffix}" for suffix in ("dylib", "plist")}
    files = set()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise BuildError(f"Unsafe package path: {member.name}")
            if member.isdir():
                continue
            if not member.isfile() or str(path) in files:
                raise BuildError(f"Unexpected package member: {member.name}")
            files.add(str(path))
    if files != expected:
        raise BuildError(f"Unexpected {scheme} payload paths: {sorted(files)}; expected {sorted(expected)}")


def find_package(directory: Path, dpkg_deb: str, scheme: str, expected: dict[str, str], env: dict[str, str]) -> Path:
    matches = []
    for package in sorted((directory / "packages").glob("*.deb")):
        metadata = read_control(checked_output([dpkg_deb, "--field", str(package)], cwd=REPO, env=env).decode("utf-8"))
        if all(metadata.get(key) == value for key, value in expected.items()):
            # Read tar data in memory; never extract paths or execute maintainer scripts.
            data = checked_output([dpkg_deb, "--fsys-tarfile", str(package)], cwd=REPO, env=env)
            verify_payload(data, scheme)
            matches.append(package)
        else:
            raise BuildError(f"Package control does not match the requested build: {package}: {metadata}")
    if len(matches) != 1:
        raise BuildError(f"Expected exactly one verified {scheme} package, found {len(matches)} in {directory / 'packages'}")
    return matches[0]


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        validate_make_path(REPO)
        env = make_environment()
        theos = discover_theos(env)
        env["THEOS"] = str(theos)
        tools = {name: shutil.which(name) for name in ("make", "dpkg-deb")}
        for name, path in tools.items():
            if path is None:
                raise BuildError(f"Required tool is not on PATH: {name}; no dependencies were installed")
        schemes = list(DEBIAN_ARCHS) if args.scheme == "both" else [args.scheme]
        if "rootless" in schemes and not any((theos / root / "rootless/package/deb.mk").is_file() and (theos / root / "rootless/package.mk").is_file() for root in ("vendor/mod", "mod")):
            raise BuildError(f"The official rootless package scheme is missing from {theos}")
        original = (REPO / "examples/HelloTweak/control").read_text(encoding="utf-8")
        fields = read_control(original)
        version = package_version(args.package_version or fields["version"])
        configs = {scheme: build_config(tools["make"], scheme, args, env) for scheme in schemes}
        run = new_run_directory(REPO)
        print(f"THEOS: {theos}\nRun directory: {run}", flush=True)
        packages = []
        for scheme in schemes:
            config = configs[scheme]
            directory = run / scheme
            minimum = config["DEPLOYMENT_TARGET"]
            source = stage_source(directory, scheme, version, minimum, original)
            command = make_command(tools["make"], theos, source, scheme, config, version)
            run_logged(command + ["example-build-info"], directory, env)
            run_logged(command + ["package"], directory, env)
            expected = {"package": fields["package"], "version": version, "architecture": DEBIAN_ARCHS[scheme], "depends": dependencies(minimum)}
            package = find_package(directory, tools["dpkg-deb"], scheme, expected, env)
            packages.append((scheme, package))
            print(f"Verified {scheme}: {expected}; install prefix: {'/var/jb' if scheme == 'rootless' else '/'}", flush=True)
        print("\nVerified release packages (not published or installed):")
        for scheme, package in packages:
            print(f"{scheme}: {package}")
        return 0
    except (BuildError, OSError, tarfile.TarError, argparse.ArgumentTypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
