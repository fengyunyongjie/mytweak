#!/usr/bin/env python3
"""Build and validate a flat, multi-architecture APT repository."""

import argparse
import bz2
import contextlib
import datetime
import email.utils
import gzip
import hashlib
import html
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import string
import subprocess
import sys
import tempfile
import zlib
from urllib.parse import quote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
INDEX_FILES = ("Packages", "Packages.gz", "Packages.bz2", "Packages.xz")
SITE_FILES = ("Release", "index.html", ".nojekyll")
ARCHITECTURES = {
    "iphoneos-arm": "rootful",
    "iphoneos-arm64": "rootless",
    "all": "通用资源",
}
HASH_FIELDS = {"md5sum": "md5", "sha1": "sha1", "sha256": "sha256"}
GENERATED_FIELDS = {"filename", "size", "md5sum", "sha1", "sha256", "sha512"}
REQUIRED_FIELDS = ("package", "version", "architecture", "maintainer", "description")


class RepoError(Exception):
    pass


def command_result(command, cwd=None, success_codes=(0,)):
    try:
        result = subprocess.run(
            [str(part) for part in command], cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            env={**os.environ, "LC_ALL": "C", "DPKG_COLORS": "never"},
        )
    except FileNotFoundError as error:
        raise RepoError(f"缺少工具 {command[0]}；请安装 dpkg。") from error
    if result.returncode not in success_codes:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RepoError(f"{command[0]} 执行失败 ({result.returncode}): {detail}")
    return result


def run(command, cwd=None):
    return command_result(command, cwd).stdout


def same_version(left, right):
    return left == right or command_result(
        ["dpkg", "--compare-versions", left, "eq", right], success_codes=(0, 1),
    ).returncode == 0


def register_identity(identities, fields, label):
    name, version, architecture = package_key(fields)
    versions = identities.setdefault((name, architecture), [])
    if any(same_version(version, other) for other in versions):
        raise RepoError(f"{label}: 重复的 (Package, Version, Architecture)，含 Debian 等价版本: {(name, version, architecture)}")
    versions.append(version)


def parse_stanzas(text, label):
    stanzas = []
    fields = {}
    previous = None
    for number, line in enumerate(text.split("\n"), 1):
        line = line.removesuffix("\r")
        if not line.strip(" \t"):
            if fields:
                stanzas.append(fields)
                fields = {}
            previous = None
        elif line.startswith((" ", "\t")):
            if previous is None:
                raise RepoError(f"{label}:{number}: 没有字段的续行")
            fields[previous] += "\n" + line[1:]
        else:
            match = re.fullmatch(r"([!-9;-~]+):[ \t]*(.*)", line)
            if not match:
                raise RepoError(f"{label}:{number}: 无效的 control 字段")
            name, value = match.groups()
            name = name.lower()
            if name in fields:
                raise RepoError(f"{label}:{number}: 重复字段 {name}")
            fields[name] = value.rstrip(" \t")
            previous = name
    if fields:
        stanzas.append(fields)
    return stanzas


def read_stanzas(path):
    try:
        return parse_stanzas(path.read_text(encoding="utf-8"), str(path))
    except (OSError, UnicodeError) as error:
        raise RepoError(f"无法读取 {path}: {error}") from error


def package_key(fields):
    try:
        return tuple(fields[name] for name in ("package", "version", "architecture"))
    except KeyError as error:
        raise RepoError(f"包记录缺少字段 {error.args[0]}") from error


def validate_metadata(fields, label):
    for name in REQUIRED_FIELDS:
        if not fields.get(name):
            raise RepoError(f"{label}: 缺少 {name}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", fields["package"]):
        raise RepoError(f"{label}: 无效的 Package")
    if fields["architecture"] not in ARCHITECTURES:
        raise RepoError(f"{label}: 不支持的架构 {fields['architecture']}")
    run(["dpkg", "--validate-version", fields["version"]])


def hashes(path):
    digest = {
        name: hashlib.new(algorithm, usedforsecurity=False)
        for name, algorithm in HASH_FIELDS.items()
    }
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            for value in digest.values():
                value.update(block)
    return {name: value.hexdigest() for name, value in digest.items()}


def safe_filename(value):
    path = PurePosixPath(value)
    if (path.is_absolute() or str(path) != value or len(path.parts) < 2
            or path.parts[0] != "debs" or path.suffix != ".deb"
            or any(part in (".", "..") for part in path.parts)
            or not all(re.fullmatch(r"[A-Za-z0-9_.+~:-]+", part) for part in path.parts)):
        raise RepoError(f"不安全或非规范的 deb 路径: {value!r}")
    return path


def discover_debs(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise RepoError(f"deb 输入必须是普通目录: {directory}")
    found = []
    for current, directories, files in os.walk(directory, followlinks=False):
        for name in sorted(directories + files):
            path = Path(current) / name
            if path.is_symlink():
                raise RepoError(f"deb 目录不接受符号链接: {path}")
        for name in sorted(files):
            path = Path(current) / name
            if path.suffix == ".deb":
                if not path.is_file():
                    raise RepoError(f"deb 必须是普通文件: {path}")
                relative = "debs/" + path.relative_to(directory).as_posix()
                safe_filename(relative)
                found.append((relative, path))
    if not found:
        raise RepoError(f"没有找到 deb 包: {directory}")
    return sorted(found)


def inspect_packages(directory):
    records = {}
    identities = {}
    for filename, path in discover_debs(directory):
        try:
            control = run(["dpkg-deb", "--field", path]).decode("utf-8")
        except UnicodeError as error:
            raise RepoError(f"{filename}: control 不是 UTF-8") from error
        stanzas = parse_stanzas(control, filename)
        if len(stanzas) != 1:
            raise RepoError(f"{filename}: control 必须只有一个记录")
        fields = stanzas[0]
        validate_metadata(fields, filename)
        if GENERATED_FIELDS.intersection(fields):
            raise RepoError(f"{filename}: control 不能包含仓库生成的索引字段")
        register_identity(identities, fields, filename)
        # Listing validates the data archive without extracting or running its scripts.
        run(["dpkg-deb", "--contents", path])
        records[filename] = {
            "fields": fields, "size": path.stat().st_size, "hashes": hashes(path),
        }
    return records


def check_baseline(stanzas, baseline):
    if baseline is None:
        return
    baseline = Path(baseline)
    if baseline.is_dir():
        baseline /= "Packages"
    previous = {}
    identities = {}
    for fields in read_stanzas(baseline):
        identity = package_key(fields)
        checksum = fields.get("sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise RepoError(f"发布基线缺少有效 SHA256: {identity}")
        run(["dpkg", "--validate-version", fields["version"]])
        register_identity(identities, fields, "发布基线")
        name, version, architecture = identity
        previous.setdefault((name, architecture), []).append((version, checksum))
    if not previous:
        raise RepoError(f"发布基线为空: {baseline}")
    for fields in stanzas:
        name, version, architecture = package_key(fields)
        for old_version, old_checksum in previous.get((name, architecture), []):
            if same_version(version, old_version) and old_checksum != fields["sha256"]:
                raise RepoError(f"禁止覆盖已发布的同版本同架构包，请先提升 Version: {package_key(fields)}")


def validate_tree(directory):
    required = set(INDEX_FILES + SITE_FILES)
    allowed = required | {"CNAME"}
    if directory.is_symlink() or not directory.is_dir():
        raise RepoError(f"发布产物必须是普通目录: {directory}")
    for current, directories, files in os.walk(directory, followlinks=False):
        for name in directories + files:
            path = Path(current) / name
            relative = path.relative_to(directory).as_posix()
            if path.is_symlink():
                raise RepoError(f"发布目录不接受符号链接: {relative}")
            if path.is_dir():
                if relative != "debs" and not relative.startswith("debs/"):
                    raise RepoError(f"发布目录包含非产物目录: {relative}")
            elif not path.is_file():
                raise RepoError(f"发布目录包含非普通文件: {relative}")
            elif relative not in allowed:
                safe_filename(relative)
    for name in required:
        if not (directory / name).is_file():
            raise RepoError(f"缺少发布产物: {name}")


def validate_release(directory, architecture_set):
    stanzas = read_stanzas(directory / "Release")
    if len(stanzas) != 1:
        raise RepoError("Release 必须是一个连续的 Deb822 记录，字段间不能插入空行")
    release = stanzas[0]
    for name in ("origin", "label", "suite", "codename", "description", "date"):
        if not release.get(name):
            raise RepoError(f"Release 缺少 {name}")
    architectures = release.get("architectures", "").split()
    if set(architectures) != architecture_set or len(architectures) != len(architecture_set):
        raise RepoError("Release Architectures 与实际包架构不一致")
    try:
        date = email.utils.parsedate_to_datetime(release["date"])
        if date.tzinfo is None:
            raise ValueError("缺少时区")
    except (ValueError, TypeError) as error:
        raise RepoError("Release Date 不是有效的带时区日期") from error
    index_hashes = {name: hashes(directory / name) for name in INDEX_FILES}
    for algorithm, field in (("md5sum", "md5sum"), ("sha1", "sha1"), ("sha256", "sha256")):
        entries = {}
        for line in release.get(field, "").splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) != 3:
                raise RepoError(f"Release {field}: 哈希条目格式错误")
            checksum, size, filename = parts
            if filename in entries or filename not in INDEX_FILES:
                raise RepoError(f"Release {field}: 重复或未知索引 {filename}")
            if (checksum != index_hashes[filename][algorithm]
                    or size != str((directory / filename).stat().st_size)):
                raise RepoError(f"Release {field}: {filename} 哈希或大小不一致")
            entries[filename] = checksum
        if set(entries) != set(INDEX_FILES):
            raise RepoError(f"Release {field}: 未完整覆盖所有索引")


def validate_repo(directory, baseline=None):
    directory = Path(directory)
    validate_tree(directory)
    records = inspect_packages(directory / "debs")
    stanzas = read_stanzas(directory / "Packages")
    indexed = set()
    identities = {}
    for fields in stanzas:
        filename = fields.get("filename", "")
        safe_filename(filename)
        if filename in indexed:
            raise RepoError(f"Packages 重复引用文件: {filename}")
        indexed.add(filename)
        record = records.get(filename)
        if record is None:
            raise RepoError(f"Packages 引用了不存在的文件: {filename}")
        register_identity(identities, fields, "Packages")
        expected_fields = set(record["fields"]) | {"filename", "size", *HASH_FIELDS}
        if set(fields) != expected_fields:
            raise RepoError(f"{filename}: 索引字段集合与 deb control 不一致")
        for name, value in record["fields"].items():
            if fields.get(name) != value:
                raise RepoError(f"{filename}: 索引 {name} 与 deb control 不一致")
        if fields.get("size") != str(record["size"]):
            raise RepoError(f"{filename}: 索引 Size 不一致")
        for name, value in record["hashes"].items():
            if fields.get(name) != value:
                raise RepoError(f"{filename}: 索引 {name} 不一致")
    if indexed != set(records):
        raise RepoError("Packages 未完整收录发布目录的所有 deb")
    raw = (directory / "Packages").read_bytes()
    for name, decoder in (
        ("Packages.gz", zlib.decompressobj(wbits=31)),
        ("Packages.bz2", bz2.BZ2Decompressor()),
        ("Packages.xz", lzma.LZMADecompressor(format=lzma.FORMAT_XZ)),
    ):
        try:
            decoded = decoder.decompress((directory / name).read_bytes(), len(raw) + 1)
        except (OSError, EOFError, lzma.LZMAError, zlib.error) as error:
            raise RepoError(f"{name} 压缩数据损坏: {error}") from error
        if decoded != raw:
            raise RepoError(f"{name} 解压后与 Packages 不一致")
        if not decoder.eof or decoder.unused_data:
            raise RepoError(f"{name} 压缩流未结束或含有额外尾数据")
    validate_release(directory, {record["fields"]["architecture"] for record in records.values()})
    check_baseline(stanzas, baseline)
    return records


def read_config(path):
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RepoError(f"无法读取源配置 {path}: {error}") from error
    names = ("origin", "label", "suite", "version", "codename", "components", "description", "url")
    if not isinstance(config, dict) or set(config) != set(names):
        raise RepoError("repo.json 必须且只能包含: " + ", ".join(names))
    for name in names:
        value = config[name]
        if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 for char in value):
            raise RepoError(f"repo.json 的 {name} 必须是非空单行文本")
    url = urlsplit(config["url"])
    if (url.scheme not in ("http", "https") or not url.hostname or url.username
            or url.password or url.query or url.fragment):
        raise RepoError("repo.json 的 url 必须是没有身份信息、查询或片段的 HTTP(S) 源地址")
    return config


def write_indexes(directory, config, records, timestamp):
    raw = run(["dpkg-scanpackages", "-m", "debs"], cwd=directory)
    (directory / "Packages").write_bytes(raw)
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as stream:
        stream.write(raw)
    (directory / "Packages.gz").write_bytes(buffer.getvalue())
    (directory / "Packages.bz2").write_bytes(bz2.compress(raw, compresslevel=9))
    (directory / "Packages.xz").write_bytes(lzma.compress(raw, preset=9))
    architectures = sorted({record["fields"]["architecture"] for record in records.values()})
    date = email.utils.format_datetime(
        datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc), usegmt=True,
    )
    lines = [f"{name.title()}: {config[name]}" for name in (
        "origin", "label", "suite", "version", "codename", "components", "description",
    )]
    lines.extend(["Architectures: " + " ".join(architectures), "Date: " + date])
    index_hashes = {name: hashes(directory / name) for name in INDEX_FILES}
    for heading, key in (("MD5Sum", "md5sum"), ("SHA1", "sha1"), ("SHA256", "sha256")):
        lines.append(heading + ":")
        for name in INDEX_FILES:
            lines.append(f" {index_hashes[name][key]} {(directory / name).stat().st_size} {name}")
    (directory / "Release").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_site(directory, config, records):
    rows = []
    for filename, record in sorted(records.items(), key=lambda item: package_key(item[1]["fields"])):
        fields = record["fields"]
        name = html.escape(fields.get("name", fields["package"]))
        package = html.escape(fields["package"])
        version = html.escape(fields["version"])
        architecture = html.escape(fields["architecture"])
        mode = ARCHITECTURES[fields["architecture"]]
        url = html.escape(quote(filename, safe="/"), quote=True)
        rows.append(
            f'<tr><td><a href="{url}">{name}</a><br><small>{package}</small></td>'
            f'<td>{version}</td><td>{mode}<br><small>{architecture}</small></td></tr>'
        )
    template = string.Template((ROOT / "site" / "index.html").read_text(encoding="utf-8"))
    page = template.substitute(
        label=html.escape(config["label"]), description=html.escape(config["description"]),
        url=html.escape(config["url"], quote=True), rows="\n".join(rows), count=len(records),
    )
    (directory / "index.html").write_text(page, encoding="utf-8")
    (directory / ".nojekyll").touch()


@contextlib.contextmanager
def output_lock(output):
    lock = output.parent / ("." + output.name + ".lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RepoError(f"输出正在使用或遗留了锁，请检查后再处理: {lock}") from error
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink()


def build_repo(debs, output, config_path, baseline=None):
    if debs.is_symlink():
        raise RepoError("deb 输入目录不能是符号链接")
    if output.is_symlink():
        raise RepoError("不能覆盖符号链接输出目录")
    debs = debs.resolve()
    output = output.resolve()
    config_path = config_path.resolve()
    for protected in (debs, ROOT, config_path):
        if protected == output or output in protected.parents:
            raise RepoError(f"输出目录不能包含输入或项目: {output}")
    if debs in output.parents:
        raise RepoError("输出目录不能位于 deb 输入目录内")
    config = read_config(config_path)
    inputs = discover_debs(debs)
    timestamp = int(os.environ.get("SOURCE_DATE_EPOCH", max(int(path.stat().st_mtime) for _, path in inputs)))
    if timestamp < 0:
        raise RepoError("SOURCE_DATE_EPOCH 不能是负数")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output_lock(output):
        backup = output.parent / ("." + output.name + ".previous")
        if backup.exists() or backup.is_symlink():
            raise RepoError(f"发现待恢复的旧产物，请检查后再生成: {backup}")
        if output.exists():
            if not output.is_dir():
                raise RepoError(f"输出不是目录: {output}")
            if any(output.iterdir()):
                # Never replace an unrelated directory or unverified existing output.
                validate_repo(output)
        with tempfile.TemporaryDirectory(prefix=".repo-build-", dir=output.parent) as temporary:
            staging = Path(temporary) / "repo"
            staging.mkdir()
            for filename, path in inputs:
                destination = staging / filename
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
            records = inspect_packages(staging / "debs")
            write_indexes(staging, config, records, timestamp)
            write_site(staging, config, records)
            validate_repo(staging, baseline)
            try:
                if output.exists():
                    output.rename(backup)
                staging.rename(output)
            except BaseException:
                if backup.exists() and not output.exists():
                    backup.rename(output)
                raise
            if backup.exists():
                shutil.rmtree(backup)
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="生成并验证隔离的发布产物")
    build.add_argument("--debs", type=Path, default=ROOT / "debs")
    build.add_argument("--output", type=Path, default=ROOT / ".build" / "repo")
    build.add_argument("--config", type=Path, default=ROOT / "repo.json")
    build.add_argument("--baseline", type=Path, help="已发布 Packages 文件或发布目录")
    validate = commands.add_parser("validate", help="验证 deb、索引、Release 和发布基线")
    validate.add_argument("--repo", type=Path, default=ROOT / ".build" / "repo")
    validate.add_argument("--baseline", type=Path, help="禁止覆盖此基线中的同版本同架构包")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            records = build_repo(args.debs, args.output, args.config, args.baseline)
            print(f"已生成并验证: {args.output.resolve()}")
        else:
            records = validate_repo(args.repo, args.baseline)
            print(f"已验证: {args.repo.resolve()}")
        architectures = sorted({record["fields"]["architecture"] for record in records.values()})
        print(f"包数: {len(records)}；实际架构: {', '.join(architectures)}")
        return 0
    except (RepoError, OSError, ValueError, OverflowError) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
