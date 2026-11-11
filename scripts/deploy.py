#!/usr/bin/env python3
"""Validate and preview a Pages snapshot; publish only with explicit consent."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "repo.py"
PUBLISH_REF = "refs/heads/gh-pages"
BASELINE_REFS = (PUBLISH_REF, "refs/remotes/origin/gh-pages")
ARTIFACT_FILES = (
    "Packages", "Packages.gz", "Packages.bz2", "Packages.xz",
    "Release", "index.html", ".nojekyll",
)
GIT_OPTIONS = (
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.fsmonitor=false",
    "-c", "core.sparseCheckout=false",
    "-c", "core.autocrlf=false",
    "-c", "core.safecrlf=false",
    "-c", "core.attributesFile=/dev/null",
    "-c", "commit.gpgSign=false",
    "-c", "push.gpgSign=false",
)


class DeployError(Exception):
    pass


def run(command, *, cwd, accepted=(0,), input_data=None):
    """Never turn an unsuccessful command into an apparent no-op."""
    command = [str(part) for part in command]
    try:
        result = subprocess.run(
            command, cwd=cwd, input=input_data,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
    except OSError as exc:
        raise DeployError(f"无法执行 {shlex.join(command)}: {exc}") from exc
    if result.returncode not in accepted:
        detail = (result.stderr + result.stdout).decode("utf-8", errors="replace").strip()
        raise DeployError(
            f"命令失败（退出码 {result.returncode}）: {shlex.join(command)}"
            + (f"\n{detail}" if detail else "")
        )
    return result


def git(directory, *arguments, accepted=(0,), input_data=None):
    return run(
        ["git", *GIT_OPTIONS, "-C", directory, *arguments], cwd=directory,
        accepted=accepted, input_data=input_data,
    )


def validate_environment():
    # Inherited Git overrides must not redirect worktree/index operations elsewhere.
    overrides = (
        "GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
    )
    found = [key for key in overrides if key in os.environ]
    if found:
        raise DeployError("请先取消会重定向 Git 的环境变量: " + ", ".join(found))


def find_baseline(requested=None):
    references = (requested,) if requested else BASELINE_REFS
    for ref in references:
        if ref not in BASELINE_REFS:
            raise DeployError("基线只能选择 refs/heads/gh-pages 或 refs/remotes/origin/gh-pages")
        present = git(ROOT, "show-ref", "--verify", "--quiet", ref, accepted=(0, 1))
        if present.returncode == 0:
            oid = git(ROOT, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout.decode().strip()
            return ref, oid
    raise DeployError(
        "找不到已有 gh-pages 发布基线；需要本地 refs/heads/gh-pages 或 "
        "refs/remotes/origin/gh-pages。dry-run 不联网，也不会创建发布分支。"
    )


def baseline_blob(oid, name, required=False):
    result = git(ROOT, "ls-tree", "-z", oid, "--", name)
    entries = [entry for entry in result.stdout.split(b"\0") if entry]
    if not entries:
        if required:
            raise DeployError(
                f"发布基线 {oid} 缺少 {name}；不能跳过同版本覆盖校验。"
            )
        return None
    if len(entries) != 1:
        raise DeployError(f"发布基线中的 {name} 不是单个普通文件")
    metadata, path = entries[0].split(b"\t", 1)
    mode, kind, _ = metadata.split()
    if path != name.encode() or kind != b"blob" or mode not in (b"100644", b"100755"):
        raise DeployError(f"发布基线中的 {name} 必须是普通文件，不能是符号链接或目录")
    return git(ROOT, "show", f"{oid}:{name}").stdout


def copy_regular(source, destination):
    if not stat.S_ISREG(source.lstat().st_mode):
        raise DeployError(f"产物必须是普通文件（不允许符号链接）: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(0o644)


def make_snapshot(source, snapshot, cname):
    if not stat.S_ISDIR(source.lstat().st_mode):
        raise DeployError(f"产物路径必须是普通目录: {source}")
    snapshot.mkdir()
    entries = {entry.name for entry in source.iterdir()}
    expected = set(ARTIFACT_FILES) | {"debs"}
    missing = expected - entries
    if missing:
        raise DeployError("缺少发布产物: " + ", ".join(sorted(missing)))
    extra = entries - expected - {"CNAME"}
    if extra:
        raise DeployError("输出目录包含非发布产物: " + ", ".join(sorted(extra)))
    for name in ARTIFACT_FILES:
        copy_regular(source / name, snapshot / name)

    debs = source / "debs"
    if not stat.S_ISDIR(debs.lstat().st_mode):
        raise DeployError(f"debs 必须是普通目录（不允许符号链接）: {debs}")
    (snapshot / "debs").mkdir()

    def walk_error(error):
        raise error

    for directory, folders, files in os.walk(debs, followlinks=False, onerror=walk_error):
        directory = Path(directory)
        for folder in folders:
            child = directory / folder
            if not stat.S_ISDIR(child.lstat().st_mode):
                raise DeployError(f"debs 中不允许符号链接或特殊目录: {child}")
        for name in sorted(files):
            path = directory / name
            if not name.endswith(".deb"):
                raise DeployError(f"debs 中包含非 deb 产物: {path}")
            copy_regular(path, snapshot / path.relative_to(source))

    # Never introduce or change a custom domain through a build artifact.
    if "CNAME" in entries:
        built_cname = source / "CNAME"
        if not stat.S_ISREG(built_cname.lstat().st_mode):
            raise DeployError("CNAME 必须是普通文件")
        if cname is None or built_cname.read_bytes() != cname:
            raise DeployError("输出 CNAME 与发布基线不同；仅允许保留已有 CNAME，不更改域名")
    if cname is not None:
        (snapshot / "CNAME").write_bytes(cname)
        (snapshot / "CNAME").chmod(0o644)


def validate_snapshot(snapshot, baseline, temporary):
    result = run(
        [sys.executable, "-I", VALIDATOR, "validate", "--repo", snapshot, "--baseline", baseline],
        cwd=temporary,
    )
    for stream, destination in ((result.stdout, sys.stdout), (result.stderr, sys.stderr)):
        if stream:
            print(stream.decode("utf-8", errors="replace").rstrip(), file=destination)


@contextmanager
def detached_worktree(temporary, oid):
    worktree = temporary / "publish-worktree"
    attempted = False
    try:
        attempted = True
        # Do not check out obsolete scripts, .gitattributes, or tool settings.
        git(ROOT, "worktree", "add", "--detach", "--no-checkout", worktree, oid)
        git(worktree, "read-tree", "--empty")
        yield worktree
    finally:
        if attempted:
            original_error = sys.exc_info()[1]
            try:
                registered = git(ROOT, "worktree", "list", "--porcelain", "-z").stdout.split(b"\0")
                target = b"worktree " + os.fsencode(worktree.resolve())
                if target in registered:
                    # --force only removes this owned temporary worktree, never pushes.
                    git(ROOT, "worktree", "remove", "--force", worktree)
            except DeployError as cleanup_error:
                if original_error is not None:
                    raise DeployError(f"{original_error}\n清理本次临时 worktree 也失败: {cleanup_error}") from cleanup_error
                raise


def stage_snapshot(snapshot, worktree):
    # Bypass all clean filters and attributes (including .git/info/attributes).
    # Besides preserving exact deb bytes, this keeps dry-run from invoking local
    # filter commands, which could themselves run scripts or contact a network.
    entries = []
    for path in sorted(snapshot.rglob("*")):
        if path.is_file():
            relative = path.relative_to(snapshot)
            copied = worktree / relative
            copy_regular(path, copied)
            oid = git(worktree, "hash-object", "-w", "--no-filters", "--", copied).stdout.strip()
            entries.append(b"100644 " + oid + b"\t" + os.fsencode(relative.as_posix()) + b"\0")
    git(worktree, "update-index", "-z", "--index-info", input_data=b"".join(entries))


def show_diff(worktree):
    print("\n发布差异（A 新增 / M 修改 / D 移除；移除项包括旧工具和配置）:", flush=True)
    for arguments in (
        ("--name-status",),
        ("--stat",),
    ):
        result = git(worktree, "diff", "--cached", "--no-ext-diff", "--no-textconv", "--no-renames",
                     "--no-color", *arguments, "HEAD", "--")
        if result.stdout:
            print(result.stdout.decode("utf-8", errors="replace").rstrip(), flush=True)
    changed = git(worktree, "diff", "--cached", "--quiet", "--no-ext-diff", "--no-textconv",
                  "HEAD", "--", accepted=(0, 1))
    return changed.returncode == 1


def confirm_publish(yes):
    if yes:
        return
    if not sys.stdin.isatty():
        raise DeployError("非交互环境不会发布；请显式使用 --publish --yes")
    try:
        answer = input("将创建提交并推送到 origin/gh-pages。输入 yes 确认: ")
    except EOFError as exc:
        raise DeployError("未获得发布确认；已取消") from exc
    if answer.strip() != "yes":
        raise DeployError("发布已取消：需要输入完整的 yes")


def remote_target():
    urls = git(ROOT, "remote", "get-url", "--push", "--all", "origin").stdout.decode().splitlines()
    if len(urls) != 1 or not urls[0] or urls[0].startswith("-") or any(c in urls[0] for c in "\r\n"):
        raise DeployError("origin 必须只有一个明确的 push URL；不支持一次推送多个仓库")
    # Use precisely the push destination, not a possibly different fetch URL.
    target = urls[0]
    if ":" not in target and not Path(target).is_absolute():
        target = str((ROOT / target).resolve())
    return target


def check_remote(target, expected_oid):
    result = git(ROOT, "ls-remote", "--exit-code", "--refs", "--", target, PUBLISH_REF, accepted=(0, 2))
    if result.returncode == 2 or not result.stdout.strip():
        raise DeployError("远端不存在 refs/heads/gh-pages；只允许更新已有发布分支，不会自动创建")
    rows = [line.split() for line in result.stdout.decode().splitlines()]
    if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != PUBLISH_REF or not re.fullmatch(r"[0-9a-fA-F]{40,64}", rows[0][0]):
        raise DeployError("无法确认远端 gh-pages 的唯一提交")
    if rows[0][0] != expected_oid:
        raise DeployError(
            "远端 gh-pages 已变化或与审阅基线不一致，停止发布以避免并发覆盖。\n"
            "请手动 git fetch origin gh-pages，并使用 "
            "--baseline-ref refs/remotes/origin/gh-pages 重新 dry-run、审阅及确认。"
        )


def publish(worktree, baseline_oid, yes):
    confirm_publish(yes)
    target = remote_target()
    check_remote(target, baseline_oid)
    message = "Update repository - " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        result = git(worktree, "-c", "core.commentChar=#", "commit", "--no-gpg-sign", "-m", message)
    except DeployError as exc:
        raise DeployError(f"创建发布提交失败（不是‘无更改’）；未推送。\n{exc}") from exc
    if result.stdout:
        print(result.stdout.decode("utf-8", errors="replace").rstrip())
    commit = git(worktree, "rev-parse", "HEAD").stdout.decode().strip()
    check_remote(target, baseline_oid)
    try:
        result = git(
            worktree, "-c", "push.followTags=false", "push", "--porcelain", "--no-follow-tags",
            "--recurse-submodules=no", "--", target, f"HEAD:{PUBLISH_REF}",
        )
    except DeployError as exc:
        raise DeployError(
            f"推送失败；未报告发布成功。临时发布提交为 {commit}，开发分支未更改。\n{exc}"
        ) from exc
    if result.stdout:
        print(result.stdout.decode("utf-8", errors="replace").rstrip())
    if result.stderr:
        print(result.stderr.decode("utf-8", errors="replace").rstrip(), file=sys.stderr)
    print(f"已推送发布提交 {commit} 到 origin/gh-pages（GitHub Pages 上线状态未检查）。")
    print(
        "本地 gh-pages / origin/gh-pages 未主动更新。下一次请先 git fetch origin gh-pages，"
        "再用 --baseline-ref refs/remotes/origin/gh-pages 重新预览。"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT / ".build" / "repo", help="已生成的纯产物目录（默认 .build/repo）")
    parser.add_argument("--baseline-ref", choices=BASELINE_REFS, help="本地已有发布基线；默认优先本地 gh-pages，再选 origin/gh-pages")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--publish", action="store_true", help="验证、显示差异，并在明确确认后创建提交和推送")
    mode.add_argument("--dry-run", action="store_true", help="只验证和预览（默认行为，不联网）")
    parser.add_argument("--yes", action="store_true", help="配合 --publish 明确确认提交及推送")
    args = parser.parse_args(argv)
    if args.yes and not args.publish:
        parser.error("--yes 只能与 --publish 一起使用")
    try:
        validate_environment()
        source = args.repo.expanduser().absolute()
        ref, oid = find_baseline(args.baseline_ref)
        print(f"模式: {'publish（等待明确确认）' if args.publish else 'dry-run（不联网、不提交、不推送）'}", flush=True)
        print(f"产物: {source}\n基线: {ref} ({oid})", flush=True)
        with tempfile.TemporaryDirectory(prefix="mytweak-deploy-") as temporary_name:
            temporary = Path(temporary_name).resolve()
            baseline = temporary / "Packages"
            baseline.write_bytes(baseline_blob(oid, "Packages", required=True))
            cname = baseline_blob(oid, "CNAME")
            snapshot = temporary / "snapshot"
            make_snapshot(source, snapshot, cname)
            validate_snapshot(snapshot, baseline, temporary)
            with detached_worktree(temporary, oid) as worktree:
                stage_snapshot(snapshot, worktree)
                if not show_diff(worktree):
                    print("无更改：产物与发布基线一致；未创建提交、未推送、未联网。")
                    return 0
                if not args.publish:
                    print("\ndry-run 完成：未创建提交、未推送、未联网。发布需 --publish，并输入 yes 或加 --yes。")
                    return 0
                publish(worktree, oid, args.yes)
        return 0
    except KeyboardInterrupt:
        print("发布已中断；本次临时资源已清理。", file=sys.stderr)
        return 130
    except (DeployError, OSError) as exc:
        print(f"部署失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
