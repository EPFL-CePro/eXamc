"""
Secure ZIP extraction helpers.

Purpose:
- Replace direct `ZipFile.extractall(...)` calls on uploaded archives.
- Enforce path and archive safety checks before writing files to disk.

Protections:
- Reject absolute paths and `..` traversal in archive member names.
- Reject symlink entries.
- Enforce maximum file count and total uncompressed size.
- Enforce destination-root containment for every extracted file.
"""

import shutil
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZipInfo


class UnsafeZipArchiveError(ValueError):
    pass


def _zipinfo_is_symlink(zip_info: ZipInfo) -> bool:
    # Unix mode bits are stored in the upper 16 bits when present.
    mode = (zip_info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _validate_zip_member_name(member_name: str) -> PurePosixPath:
    member_path = PurePosixPath(member_name)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise UnsafeZipArchiveError(f"Unsafe archive member path: {member_name}")
    return member_path


def safe_extract_zip(
    archive: ZipFile,
    destination: str | Path,
    *,
    max_files: int = 20000,
    max_total_uncompressed_size: int = 2 * 1024 * 1024 * 1024,
) -> list[Path]:
    destination_root = Path(destination).resolve()
    destination_root.mkdir(parents=True, exist_ok=True)

    members = archive.infolist()
    if len(members) > max_files:
        raise UnsafeZipArchiveError(
            f"Archive contains too many members ({len(members)} > {max_files})."
        )

    total_size = 0
    validated_members: list[tuple[ZipInfo, Path]] = []

    for zip_info in members:
        member_path = _validate_zip_member_name(zip_info.filename)

        if _zipinfo_is_symlink(zip_info):
            raise UnsafeZipArchiveError(
                f"Symlink entries are not allowed in uploaded archives: {zip_info.filename}"
            )

        total_size += int(zip_info.file_size or 0)
        if total_size > max_total_uncompressed_size:
            raise UnsafeZipArchiveError(
                "Archive uncompressed size exceeds allowed limit."
            )

        target_path = (destination_root / Path(*member_path.parts)).resolve()
        try:
            target_path.relative_to(destination_root)
        except ValueError as exc:
            raise UnsafeZipArchiveError(
                f"Archive member escapes extraction root: {zip_info.filename}"
            ) from exc

        validated_members.append((zip_info, target_path))

    extracted_paths: list[Path] = []
    for zip_info, target_path in validated_members:
        if zip_info.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(zip_info, "r") as source, open(target_path, "wb") as target:
            shutil.copyfileobj(source, target)
        extracted_paths.append(target_path)

    return extracted_paths
