#!/usr/bin/env python3
"""Export, import, and verify the local Tushare recheck data snapshot.

The raw Parquet cache is intentionally kept outside Git.  This tool creates a
portable tarball with a SHA-256 manifest so the same local data can be moved to
another computer without downloading it again.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "quantlab" / ".quantlab" / "cache" / "research" / "cn_equity"
DEFAULT_SOURCE = Path(
    os.environ.get("FACTOR_RESEARCH_CACHE_ROOT", str(DEFAULT_CACHE_ROOT))
).expanduser()
DEFAULT_ARCHIVE = PROJECT_ROOT / "data" / "local_recheck" / "factor-local-recheck-data.tar.gz"
DEFAULT_MANIFEST = PROJECT_ROOT / "research_reports" / "platform_alignment" / "local_recheck_data_manifest.json"
ARCHIVE_ROOT = "cn_equity"
MANIFEST_NAME = "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(root: Path) -> Iterable[tuple[Path, str]]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path, path.relative_to(root).as_posix()


def build_manifest(source: Path) -> dict[str, Any]:
    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Data root does not exist: {source}")

    files: list[dict[str, Any]] = []
    for path, relative in iter_files(source):
        files.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema_version": 1,
        "source_root": "quantlab/.quantlab/cache/research/cn_equity",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
        "total_bytes": sum(item["size"] for item in files),
        "files": files,
    }


def manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_manifest(manifest: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(manifest_bytes(manifest))


def add_manifest(archive: tarfile.TarFile, manifest: dict[str, Any]) -> None:
    payload = manifest_bytes(manifest)
    info = tarfile.TarInfo(MANIFEST_NAME)
    info.size = len(payload)
    info.mtime = 0
    archive.addfile(info, io.BytesIO(payload))


def export_archive(source: Path, output: Path) -> dict[str, Any]:
    manifest = build_manifest(source)
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".part", dir=output.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with tarfile.open(temporary, mode="w:gz", compresslevel=1) as archive:
            add_manifest(archive, manifest)
            for path, relative in iter_files(source.resolve()):
                archive.add(path, arcname=f"{ARCHIVE_ROOT}/{relative}", recursive=False)
        os.replace(temporary, output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return {"archive": str(output), **{key: manifest[key] for key in ("file_count", "total_bytes")}}


def load_archive_manifest(archive_path: Path) -> tuple[tarfile.TarFile, dict[str, Any]]:
    archive = tarfile.open(archive_path, mode="r:gz")
    try:
        member = archive.getmember(MANIFEST_NAME)
        handle = archive.extractfile(member)
        if handle is None:
            raise RuntimeError(f"Archive manifest is not readable: {archive_path}")
        manifest = json.loads(handle.read().decode("utf-8"))
        if manifest.get("schema_version") != 1:
            raise RuntimeError(f"Unsupported data manifest version: {manifest.get('schema_version')}")
        return archive, manifest
    except Exception:
        archive.close()
        raise


def safe_archive_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"Unsafe archive member path: {name}")
    return path


def expected_manifest_paths(manifest: dict[str, Any]) -> set[str]:
    return {f"{ARCHIVE_ROOT}/{item['path']}" for item in manifest["files"]}


def verify_archive(archive_path: Path) -> dict[str, Any]:
    archive_path = archive_path.expanduser().resolve()
    archive, manifest = load_archive_manifest(archive_path)
    try:
        members = {safe_archive_name(member.name).as_posix(): member for member in archive.getmembers()}
        expected = expected_manifest_paths(manifest)
        missing = sorted(expected - members.keys())
        if missing:
            raise RuntimeError(f"Archive is missing {len(missing)} data files; first: {missing[0]}")
        for item in manifest["files"]:
            name = f"{ARCHIVE_ROOT}/{item['path']}"
            member = members[name]
            if not member.isfile():
                raise RuntimeError(f"Archive member is not a file: {name}")
            handle = archive.extractfile(member)
            if handle is None:
                raise RuntimeError(f"Archive member is not readable: {name}")
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            if digest.hexdigest() != item["sha256"]:
                raise RuntimeError(f"SHA-256 mismatch in archive: {name}")
    finally:
        archive.close()
    return {
        "archive": str(archive_path),
        "file_count": manifest["file_count"],
        "total_bytes": manifest["total_bytes"],
        "status": "verified",
    }


def verify_tree(source: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    source = source.expanduser().resolve()
    missing: list[str] = []
    mismatched: list[str] = []
    for item in manifest["files"]:
        path = source / Path(item["path"])
        if not path.is_file():
            missing.append(item["path"])
            continue
        if path.stat().st_size != item["size"] or sha256_file(path) != item["sha256"]:
            mismatched.append(item["path"])
    if missing or mismatched:
        details = []
        if missing:
            details.append(f"missing={len(missing)}")
        if mismatched:
            details.append(f"mismatched={len(mismatched)}")
        raise RuntimeError("Local data verification failed: " + ", ".join(details))
    return {
        "source": str(source),
        "file_count": manifest["file_count"],
        "total_bytes": manifest["total_bytes"],
        "status": "verified",
    }


def import_archive(archive_path: Path, destination_root: Path, replace: bool) -> dict[str, Any]:
    archive_path = archive_path.expanduser().resolve()
    destination_root = destination_root.expanduser().resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    target = destination_root / ARCHIVE_ROOT
    if target.exists() and not replace:
        raise RuntimeError(f"Destination already exists; use --replace explicitly: {target}")

    archive, manifest = load_archive_manifest(archive_path)
    staging = Path(tempfile.mkdtemp(prefix=".local-recheck-import-", dir=destination_root))
    try:
        for member in archive.getmembers():
            safe_archive_name(member.name)
            if member.name == MANIFEST_NAME:
                continue
            if not member.name.startswith(f"{ARCHIVE_ROOT}/"):
                raise RuntimeError(f"Unexpected archive member: {member.name}")
            if not member.isfile() and not member.isdir():
                raise RuntimeError(f"Unsupported archive member type: {member.name}")
            archive.extract(member, path=staging)
        archive.close()
        result = verify_tree(staging / ARCHIVE_ROOT, manifest)
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(staging / ARCHIVE_ROOT), str(target))
        result["destination"] = str(target)
        return result
    finally:
        archive.close()
        shutil.rmtree(staging, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser("manifest", help="write a SHA-256 manifest for the local data")
    manifest.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    manifest.add_argument("--output", type=Path, default=DEFAULT_MANIFEST)

    export = subparsers.add_parser("export", help="create a portable tar.gz snapshot")
    export.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    export.add_argument("--output", type=Path, default=DEFAULT_ARCHIVE)

    verify = subparsers.add_parser("verify", help="verify an archive or restored local data tree")
    verify.add_argument("--archive", type=Path)
    verify.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    verify.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)

    restore = subparsers.add_parser("import", help="restore a snapshot into the research cache")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument(
        "--destination-root",
        type=Path,
        default=DEFAULT_SOURCE.parent,
        help="directory that will contain the restored cn_equity directory",
    )
    restore.add_argument("--replace", action="store_true", help="replace an existing cn_equity directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "manifest":
        manifest = build_manifest(args.source)
        write_manifest(manifest, args.output)
        print(json.dumps({"manifest": str(args.output.resolve()), "file_count": manifest["file_count"], "total_bytes": manifest["total_bytes"]}, ensure_ascii=False, indent=2))
    elif args.command == "export":
        print(json.dumps(export_archive(args.source, args.output), ensure_ascii=False, indent=2))
    elif args.command == "verify":
        if args.archive:
            result = verify_archive(args.archive)
        else:
            if not args.manifest.is_file():
                raise SystemExit(f"Manifest not found: {args.manifest}; run the manifest command first")
            result = verify_tree(args.source, json.loads(args.manifest.read_text(encoding="utf-8")))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "import":
        print(json.dumps(import_archive(args.archive, args.destination_root, args.replace), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
