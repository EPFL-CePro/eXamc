"""
Celery tasks of examc_app.

Celery's autodiscovery imports ``examc_app.tasks``, so every module of the package is imported here: this registers
their tasks with the worker. The tasks are re-exported, so ``from examc_app.tasks import ...`` keeps working.

Each task keeps its former name (``examc_app.tasks.<function>``) through ``name=``, so the beat schedule, the
routes and the tasks already queued still find it.
"""

from examc_app.tasks.correction import (  # noqa: F401
    amc_annotate_task,
    amc_import_from_review_task,
)
from examc_app.tasks.exports import (  # noqa: F401
    finish_marked_files_zip,
    generate_marked_copy_pdf,
    generate_marked_files_zip,
)
from examc_app.tasks.imports import import_csv_data, import_exam_scans  # noqa: F401
from examc_app.tasks.maintenance import (  # noqa: F401
    cleanup_review_locks,
    fail_stale_jobs,
)
from examc_app.tasks.preparation import (
    compile_exam_preview_task,  # noqa: F401
    generate_final_exam_files_task,  # noqa: F401
    update_amc_scoring_task,  # noqa: F401
)
from examc_app.tasks.stats import generate_statistics  # noqa: F401
