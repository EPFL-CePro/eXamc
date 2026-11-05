import logging

from django.contrib.auth.models import User
from django.db.models import Q

from examc_app.models import Exam, ExamUser
from examc_app.services.person_directory import get_people_by_sciper

logger = logging.getLogger(__name__)

def user_allowed(exam: Exam, user_id):
    user = User.objects.get(pk=user_id)
    exam_users = ExamUser.objects.filter(Q(user=user) & (Q(exam=exam) | Q(exam__in=exam.common_exams.all())))
    return bool(exam_users or user.is_superuser)

def get_course_teachers_string(teachers):
    teachers_list = teachers.split('|')
    teachers_str = ''
    for t in teachers_list:
        if t:
            if teachers_str != '':
                teachers_str += ','
            teachers_str += t.split(';')[2]
    return teachers_str

def add_course_teachers(scipers: list[str]) -> list[User]:
    """
    Return the users of the given teachers, creating the missing ones from the EPFL directory.
    Teachers not found in the directory or without a valid email are skipped.
    """
    scipers = [str(sciper).strip() for sciper in scipers if sciper]
    people = get_people_by_sciper(scipers)

    teachers_list = []
    for sciper in scipers:
        person = people.get(sciper)
        if person is None or not person.email:
            logger.warning("Teacher %s not found in the EPFL directory or without email: skipped", sciper)
            continue

        user = User.objects.filter(email__iexact=person.email).first()
        if user is None:
            user = User.objects.create(
                username=person.sciper,
                first_name=person.first_name,
                last_name=person.last_name,
                email=person.email,
                is_active=True,
            )

        teachers_list.append(user)

    return teachers_list

def search_and_replace(file_path, search_word, replace_word):
   with open(file_path, 'r') as file:
      file_contents = file.read()

      updated_contents = file_contents.replace(search_word, replace_word)

   with open(file_path, 'w') as file:
      file.write(updated_contents)