# examc_app/utils/amc/amc_build_retention.py

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import logging

from django.db import transaction

from examc_app.models import ExamBuild

logger = logging.getLogger(__name__)

READY_STATUS = "ready"
KEEP_SUCCESSFUL = 3
KEEP_NON_READY = 5


@dataclass
class BuildRetentionDecision:
    build_id: int
    exam_id: int
    version: int
    status: str
    keep: bool
    reasons: list[str] = field(default_factory=list)


def _build_keep_reasons(build: ExamBuild) -> list[str]:
    reasons = []

    if build.is_locked:
        reasons.append("locked")

    if build.copies.exists():
        reasons.append("has_copies")

    if build.scan_pages.exists():
        reasons.append("has_scan_pages")

    if build.score_results.exists():
        reasons.append("has_score_results")

    return reasons


def get_exam_build_retention_decisions(exam, *, exclude_build_id: int | None = None):
    builds = list(exam.builds.all().order_by("-created_at", "-id"))

    keep_ids = set()
    reasons_by_id = {}

    def mark_keep(build, reason: str):
        keep_ids.add(build.id)
        reasons_by_id.setdefault(build.id, [])
        if reason not in reasons_by_id[build.id]:
            reasons_by_id[build.id].append(reason)

    # Hard protection
    for build in builds:
        for reason in _build_keep_reasons(build):
            mark_keep(build, reason)

    # Latest and rolling ready builds
    ready_builds = [b for b in builds if b.status == READY_STATUS]
    if ready_builds:
        mark_keep(ready_builds[0], "latest_ready")

    for build in ready_builds[:KEEP_SUCCESSFUL]:
        mark_keep(build, f"last_{KEEP_SUCCESSFUL}_ready")

    # Rolling non-ready builds
    non_ready_builds = [b for b in builds if b.status != READY_STATUS]
    for build in non_ready_builds[:KEEP_NON_READY]:
        mark_keep(build, f"last_{KEEP_NON_READY}_non_ready")

    # Explicit safety exclusion
    if exclude_build_id is not None:
        for build in builds:
            if build.id == exclude_build_id:
                mark_keep(build, "excluded_explicitly")
                break

    decisions = []
    for build in builds:
        decisions.append(
            BuildRetentionDecision(
                build_id=build.id,
                exam_id=build.exam_id,
                version=build.version,
                status=build.status,
                keep=build.id in keep_ids,
                reasons=reasons_by_id.get(build.id, []),
            )
        )

    return decisions


def _delete_build_files(build: ExamBuild) -> dict:
    deleted = []
    failed = []

    shared_project_path = Path(build.project_path).resolve() if build.project_path else None

    paths = [
        build.latex_main_path,
        build.compiled_pdf_path,
        build.amc_log_path,
        build.xy_path,
    ]

    seen = set()
    for raw in paths:
        if not raw:
            continue

        path = Path(raw)

        try:
            resolved = path.resolve(strict=False)
        except Exception:
            resolved = path

        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)

        # Never delete files inside the shared persistent project folder
        if shared_project_path is not None:
            try:
                resolved.relative_to(shared_project_path)
                continue
            except ValueError:
                pass

        try:
            if path.is_dir():
                shutil.rmtree(path)
                deleted.append(str(path))
            elif path.exists():
                path.unlink()
                deleted.append(str(path))
        except Exception as exc:
            failed.append({"path": str(path), "error": str(exc)})
            logger.warning("Failed to delete %s for build %s: %s", path, build.id, exc)

    return {"deleted_paths": deleted, "failed_paths": failed}


@transaction.atomic
def delete_exam_build(build: ExamBuild, *, delete_files: bool = True) -> dict:
    reasons = _build_keep_reasons(build)
    if reasons:
        return {
            "deleted": False,
            "build_id": build.id,
            "reasons": reasons,
        }

    file_result = {"deleted_paths": [], "failed_paths": []}
    if delete_files:
        file_result = _delete_build_files(build)

    build_id = build.id
    build.delete()

    return {
        "deleted": True,
        "build_id": build_id,
        **file_result,
    }


def cleanup_exam_builds(
    exam,
    *,
    dry_run: bool = True,
    delete_files: bool = True,
    exclude_build_id: int | None = None,
) -> dict:
    decisions = get_exam_build_retention_decisions(
        exam,
        exclude_build_id=exclude_build_id,
    )

    to_delete_ids = [d.build_id for d in decisions if not d.keep]

    result = {
        "exam_id": exam.id,
        "dry_run": dry_run,
        "kept": [d.__dict__ for d in decisions if d.keep],
        "to_delete": [d.__dict__ for d in decisions if not d.keep],
        "deleted": [],
    }

    if dry_run:
        return result

    builds = {
        b.id: b for b in ExamBuild.objects.filter(id__in=to_delete_ids)
    }

    for build_id in to_delete_ids:
        if exclude_build_id is not None and build_id == exclude_build_id:
            continue
        build = builds.get(build_id)
        if not build:
            continue
        result["deleted"].append(
            delete_exam_build(build, delete_files=delete_files)
        )

    return result