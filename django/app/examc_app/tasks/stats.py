"""Tasks that compute the statistics of an exam.

Named ``stats`` rather than ``statistics`` so it can never be mistaken for the standard library module.
"""

from celery import shared_task
from celery_progress.backend import ProgressRecorder, logger
from django.db.models import Sum
from django.utils import timezone

from examc_app.models import Exam
from examc_app.services.jobs import update_job_progress
from examc_app.utils.generate_statistics_functions import generate_exam_stats


@shared_task(bind=True, name="examc_app.tasks.generate_statistics")
def generate_statistics(self,exam_pk: int):
    try:
        exam = Exam.objects.get(pk=exam_pk)
        logger.info(timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")+" : Start generating statistics ---> ")

        progress_recorder = ProgressRecorder(self)

        # update/init overall and common exams if common
        if exam.common_exams.all():
            overall_exam = exam.get_overall_exam_or_default()
            nb_common = len(overall_exam.common_exams.all())+1
            process_count = nb_common*5-nb_common
            process_number = 0
            print(process_number)
            progress_recorder.set_progress(process_number, process_count, description='Updating common exams...')
            #overall_exam=update_overall_common_exam(exam)
            overall_exam.present_students = overall_exam.common_exams.aggregate(sum_present=Sum('present_students'))['sum_present']
            overall_exam.save()
            process_number = generate_exam_stats(overall_exam,progress_recorder,process_number,process_count)
            print("************** "+str(overall_exam.present_students))
        else:
            process_number = 0
            process_count = 5
            progress_recorder.set_progress(0, process_count, description='')
            process_number = generate_exam_stats(exam,progress_recorder,process_number,process_count)

        logger.info(timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")+" :  -- > End generating stats !")

        process_number += 1
        progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
            process_count) + 'Done!')
        return ' Process finished.'

    except Exception as exception:
        logger.exception("Stats generation failed")
        update_job_progress(self, error=f"Error during stats generation: {exception}", error_type=type(exception).__name__)
