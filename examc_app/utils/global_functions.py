import datetime
import os.path
import re
import shutil
import unicodedata

import pypandoc
from celery import shared_task
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.signing import Signer
from django.db.models import Q, Max
from django.db.models.fields import IntegerField
from django.db.models.functions import Cast
from num2words import num2words

from django.conf import settings
from examc_app.models import ExamUser, ReviewLock
from examc_app.utils.amc_functions import get_amc_project_path, amc_update_documents, get_amc_exam_pdf_url
from examc_app.utils.epflldap.ldap_search import ldap_search_by_sciper

def user_allowed(exam, user_id):
    user = User.objects.get(pk=user_id)
    exam_users = ExamUser.objects.filter(Q(user=user) & (Q(exam=exam) | Q(exam__in=exam.common_exams.all())))
    if exam_users or user.is_superuser:
        return True
    else:
        return False

def get_course_teachers_string(teachers):
    teachers_list = teachers.split('|')
    teachers_str = ''
    for t in teachers_list:
        if t:
            if teachers_str != '':
                teachers_str += ','
            teachers_str += t.split(';')[2]
    return teachers_str

def add_course_teachers_ldap(teachers):
    teachers_split = teachers.split('|')
    teachers_list = []
    for teacher_str in teachers_split:
        if teacher_str:
            email = teacher_str.split(';')[1]
            users = User.objects.filter(email=email).all()
            if users:
                user = users.first()
            else:
                sciper = teacher_str.split(';')[0]
                user_entry = ldap_search_by_sciper(sciper)

                user = User()

                user.username = user_entry['uniqueidentifier'][0]
                user.first_name = user_entry['givenName'][0]
                user.last_name = user_entry['sn'][0]
                user.email = user_entry['mail'][0]
                user.is_active = True
                user.save()

            teachers_list.append(user)
    return teachers_list


def convert_html_to_latex(html_string):

    # Convert HTML to LaTeX using Pandoc with the custom filter
    latex_content = pypandoc.convert_text(
        html_string,
        'latex',
        format='html',
    )

    # remove itemsep of itemize if exist
    latex_content = latex_content.replace("\\begin{itemize}","\\begin{itemize}[noitemsep]")
    # remove \tightlist
    latex_content = latex_content.replace("\\tightlist","")
    # add total_pages command if exist
    latex_content = latex_content.replace("{[}TOTAL\\_PAGES{]}","\\totalPages\\")
    # remove verbatim for latex code parts
    latex_content = latex_content.replace("\\begin{verbatim}",'')
    latex_content = latex_content.replace("\\end{verbatim}", '')
    latex_content = latex_content.replace("\\$\\$", '$')

    if latex_content.startswith("$"):
        i = 1
    else:
        i = 0
    content_formulas_list = latex_content.split("$")
    for formula in content_formulas_list:
        if i%2 != 0:
            new_text = formula.replace("\\","").replace('textbackslash ','\\')
            latex_content = latex_content.replace(formula,new_text)
        i += 1

    return latex_content

def exam_generate_preview(exam):
    amc_project_path = get_amc_project_path(exam, False)
    if amc_project_path:

        # copy exam_template.tex
        shutil.copy(amc_project_path + "/exam_template.tex", amc_project_path + "/exam.tex")

        # update first_page_instructions.tex
        instruction = exam.first_page_text
        instruction_tex = convert_html_to_latex(instruction.encode('utf-8'))
        tex_file = open(amc_project_path+"/first_page_instruction.tex", "w")
        tex_file.write(instruction_tex)
        tex_file.close()

        sections_tex_input = ''
        sections_file = open(amc_project_path+"/sections.tex", "w")
        # update sections, questions and answers
        for section in exam.sections.all():
            section_id = section.section_number
            shutil.copy(amc_project_path+"/section_header_template.tex",amc_project_path+"/section_header_"+str(section_id)+".tex")

            # section header text
            header = section.header_text
            header_tex = convert_html_to_latex(header.encode('utf-8'))
            search_and_replace(amc_project_path+"/section_header_"+str(section_id)+".tex","<HEADER-TEXT>",header_tex)
            sections_tex_input += "\n \\input{./section_header_"+str(section_id)+".tex}"

            # section title
            search_and_replace(amc_project_path+"/section_header_"+str(section_id)+".tex","<HEADER-TITLE>",section.title)

            # questions
            section_file = open(amc_project_path + "/section_" + str(section_id) + ".tex",'w')
            for question in section.questions.all():
                section_file.write("\\element{section_"+str(section_id)+"}{\n")
                if question.question_type.code == 'OPEN':
                    nb_points = question.answers.all().exclude(code="BOX").annotate(code_int = Cast('code', output_field=IntegerField())).aggregate(nb_points=Max('code_int'))['nb_points']
                    section_file.write("{")
                    section_file.write("\\renewcommand{\\AMCbeginQuestion}[2]{\\QuestionText{#1}}"
                                       "\\def\\QuestionText{\\TEXT}"
                                       "\\def\\TEXT#1{}"
                                       "\\def\\NOTEXT#1{}"
                                       "\\setlength\\parindent{0pt})"
                                       "\\addtocounter{AMCquestionaff}{1}")

                    section_file.write("\\begin{description} \n")
                    section_file.write("\\item[Question~\\theAMCquestionaff :] \\textit{("+str(nb_points)+" pts)} \n")
                    section_file.write("\\end{description} \n")
                    num_word = num2words(nb_points).capitalize()
                    section_file.write("\\corrector"+num_word+"{"+question.code+"}{~} \n")
                    section_file.write("\\correctorStop \n")
                    section_file.write("\\noindent \n")
                    section_file.write(convert_html_to_latex(question.question_text))
                    section_file.write("} \n \n")
                else:
                    question_cmd = 'question'
                    question_txt = convert_html_to_latex(question.question_text)
                    if question.question_type.code == 'MCQ':
                        question_cmd = 'questionmult'

                    section_file.write("\\begin{"+question_cmd+"}{"+question.code+"}\n")
                    section_file.write(question_txt+"\n")

                    # answers
                    if question.question_type.code == 'TF':
                        section_file.write("\\begin{choiceshoriz}[o]")
                        first_answer = question.answers.first()
                        if first_answer.is_correct and first_answer.code == 'TRUE':
                            section_file.write("\\correctchoice{TRUE}\n")
                            section_file.write("\\wrongchoice{FALSE}\n")
                        else:
                            section_file.write("\\wrongchoice{TRUE}\n")
                            section_file.write("\\correctchoice{FALSE}\n")
                        section_file.write("\\end{choiceshoriz}")
                    else:
                        section_file.write("\\begin{choices}\n")
                        for answer in question.answers.all():
                            answer_txt = convert_html_to_latex(answer.answer_text)
                            if answer.is_correct:
                                section_file.write("\\correctchoice{"+answer_txt+"}\n")
                            else:
                                section_file.write("\\wrongchoice{"+answer_txt+"}\n")
                        section_file.write("\\end{choices}\n")


                    section_file.write("\\end{"+question_cmd+"}\n")
                section_file.write("}\n\n")

            sections_tex_input += "\n \\insertgroup{section_"+str(section_id)+"}"

            section_file.close()
            sections_file.write("\\input{section_" + str(section_id) + ".tex} \n")

        sections_file.close()

        #add sections to exam.tex main file
        search_and_replace(amc_project_path+"/exam.tex","<SECTIONS>",sections_tex_input)

        # compile exam.tex main file
        result = amc_update_documents(exam,0,False,True)
        if 'ERR' in result:
            amc_log_file_path = amc_project_path + "/amc-compiled.log"
            return amc_log_file_path
        else:
            file_url = get_amc_exam_pdf_url(exam)
            return file_url

    return None

def search_and_replace(file_path, search_word, replace_word):
   with open(file_path, 'r') as file:
      file_contents = file.read()

      updated_contents = file_contents.replace(search_word, replace_word)

   with open(file_path, 'w') as file:
      file.write(updated_contents)

def update_folders_paths(old_path,new_path):

    if os.path.exists(str(settings.SCANS_ROOT)+old_path):
        shutil.move(str(settings.SCANS_ROOT)+old_path, str(settings.SCANS_ROOT)+new_path)
    if os.path.exists(str(settings.MARKED_SCANS_ROOT)+old_path):
        shutil.move(str(settings.MARKED_SCANS_ROOT)+old_path, str(settings.MARKED_SCANS_ROOT)+new_path)
    if os.path.exists(str(settings.AMC_PROJECTS_ROOT)+old_path):
        shutil.move(str(settings.AMC_PROJECTS_ROOT)+old_path, str(settings.AMC_PROJECTS_ROOT)+new_path)



def safe_filename_part(s: str) -> str:
    # 1) normalize unicode (splits accents from letters)
    s = unicodedata.normalize("NFKD", s)
    # 2) drop diacritics by encoding to ASCII
    s = s.encode("ascii", "ignore").decode("ascii")
    # 3) spaces -> underscores
    s = s.replace(" ", "_")
    # 4) keep only safe chars (letters, digits, underscore, dash, dot)
    s = re.sub(r"[^A-Za-z0-9_.-]+", "", s)
    # 5) avoid empty parts
    return s or "unknown"