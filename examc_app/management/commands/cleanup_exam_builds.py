# examc_app/management/commands/cleanup_exam_builds.py

from django.core.management.base import BaseCommand, CommandError
from examc_app.models import Exam
from examc_app.utils.amc.amc_build_retention import cleanup_exam_builds


class Command(BaseCommand):
    help = "Cleanup old exam builds according to retention policy."

    def add_arguments(self, parser):
        parser.add_argument("--exam-id", type=int)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--keep-files", action="store_true")
        parser.add_argument("--exclude-build-id", type=int)

    def handle(self, *args, **options):
        exam_id = options.get("exam_id")
        dry_run = not options.get("apply")
        delete_files = not options.get("keep_files")
        exclude_build_id = options.get("exclude_build_id")

        exams = Exam.objects.all()
        if exam_id is not None:
            exams = exams.filter(id=exam_id)
            if not exams.exists():
                raise CommandError(f"Exam {exam_id} not found")

        for exam in exams:
            result = cleanup_exam_builds(
                exam,
                dry_run=dry_run,
                delete_files=delete_files,
                exclude_build_id=exclude_build_id,
            )

            self.stdout.write(
                f"Exam {exam.id}: keep={len(result['kept'])}, delete={len(result['to_delete'])}"
            )

            for item in result["to_delete"]:
                self.stdout.write(
                    f"  candidate build={item['build_id']} version={item['version']} "
                    f"status={item['status']} reasons={item['reasons']}"
                )

            for item in result["kept"]:
                self.stdout.write(
                    f"  keep build={item['build_id']} version={item['version']} "
                    f"status={item['status']} reasons={item['reasons']}"
                )