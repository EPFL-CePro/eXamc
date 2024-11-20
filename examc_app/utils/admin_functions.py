import csv
import json

from django.contrib.auth.models import User, Group

from examc_app.models import Exam, Course, AcademicYear, Semester, ExamUser
from examc_app.utils.epflldap import ldap_search


def parse_exams_data_csv(csv_file):
    try:
        csv_reader = csv.reader(csv_file.read().decode('utf-8').splitlines(), delimiter=';')

        headers = next(csv_reader)

        for row in csv_reader:
            code_index = headers.index('COURSE_CODE')
            name_index = headers.index('COURSE_NAME')
            year_index = headers.index('YEAR')
            semester_index = headers.index('SEMESTER')
            date_index = headers.index('EXAM_DATE')
            sciper_index = headers.index('TEACHER_SCIPER')
            firstname_index = headers.index('TEACHER_FIRSTNAME')
            lastname_index = headers.index('TEACHER_LASTNAME')
            email_index = headers.index('TEACHER_EMAIL')
            reviewer_index = headers.index('REVIEWER')

            code = row[code_index]
            name = row[name_index]
            semester = int(row[semester_index])
            year = row[year_index]
            exam_date = row[date_index]
            if not exam_date:
                exam_date = None

            acad_year = AcademicYear.objects.filter(code=year).first()
            sem = Semester.objects.filter(code=semester).first()
            exam, created = Exam.objects.get_or_create(code=code,name=name,semester=sem,year=acad_year,date=exam_date)
            if created:
                exam.save()

            user_sciper = row[sciper_index]
            user_firstname = row[firstname_index]
            user_lastname = row[lastname_index]
            user_email = row[email_index]

            user=None
            users = User.objects.filter(email=user_email)
            if not users:
                user, created = User.objects.get_or_create(username=user_sciper,first_name=user_firstname,last_name=user_lastname,email=user_email)
                user.is_staff=True
                user.save()
            else:
                user = users.first()

            if row[reviewer_index] == '1':
                group_name = "Reviewer"
            else:
                group_name = "Teacher"

            exam_user = ExamUser()
            exam_user.user = user
            exam_user.group = Group.objects.get(name=group_name)
            exam_user.exam = exam
            exam_user.save()

    except Exception as e:
        return f"CSV error : {e}"


def parse_courses_data_json(json_byte_data):
    json_data = json_byte_data.decode('ISO-8859-1')
    data = json.loads(json_data)
    i = 0
    for line in data:
        if not (line["course"]["courseCode"] == "Unspecified Code" or line["course"]["courseCode"] == ""):

            course = Course()
            course.code = line["course"]["courseCode"]
            course.name = line["course"]["subject"]["name"]["fr"]

            if line["course"]["gps"]:
                term = line["course"]["gps"][0]["term"]["code"]
                if term == 'ETE':
                    course.semester = Semester.objects.filter(code=2).first()
                else:
                    course.semester = Semester.objects.filter(code=1).first()

                year = line["course"]["gps"][0]["acad"]["code"]
                course.year = AcademicYear.objects.filter(code=year).first()

            teachers_str = ''
            for teacher in line["course"]["professors"]:
                ldap_teacher = ldap_search.ldap_search_by_sciper(teacher["sciper"])

                if ldap_teacher:
                    if teachers_str:
                        teachers_str += "|"

                    teachers_str += ldap_teacher['uniqueIdentifier'][0] + ";"
                    if 'mail' in ldap_teacher:
                        teachers_str += ldap_teacher['mail'][0] + ";"
                    else:
                        teachers_str += ";"
                    teachers_str += ldap_teacher['cn'][0]

            course.teachers = teachers_str
            course.save()

            i += 1
            print("line : " + str(i) + "/" + str(len(data)))
            print("  - course : " + course.code)

    return 'ok'
