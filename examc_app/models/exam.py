###########################
# EXAM
###########################
import json

from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords
from django.db.models import Count


class AcademicYear(models.Model):
    """ Stores academic year data """
    code = models.CharField(max_length=9,blank=False)
    name = models.CharField(max_length=100,blank=False)

class Semester(models.Model):
    """ Stores academic year data """
    code = models.IntegerField(blank=False)
    name = models.CharField(max_length=100,blank=False)

class Exam(models.Model):
    """
    Stores exam data, related to :model:`auth.User` and :model:`examc_app.Exam`
    """
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    semester = models.ForeignKey(Semester, on_delete=models.RESTRICT,related_name='exams',)
    year = models.ForeignKey(AcademicYear, on_delete=models.RESTRICT,related_name='exams')
    date = models.DateField(default=timezone.now, blank=True,null=True)
    #users = models.ManyToManyField(User, blank=True)
    present_students = models.IntegerField(default=0)
    common_exams = models.ManyToManyField("self", blank=True)
    overall = models.BooleanField(default=0)
    indiv_formula = models.CharField(max_length=100, blank=True,null=True)
    pages_by_copy = models.CharField(max_length=10000, blank=True,null=True)
    first_page_text = models.TextField(default='', null=True, blank=True)
    review_option = models.BooleanField(default=0)
    amc_option = models.BooleanField(default=0)
    res_and_stats_option = models.BooleanField(default=0)
    prep_option = models.BooleanField(default=0)
    pdf_catalog_name = models.CharField(max_length=200, blank=True,null=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = ('code', 'date')
        ordering = ['-year', '-semester', 'code']
        verbose_name = "Exam"

        # for permissions linked to exam and user group
        permissions = [
            ("review",   "Can review this exam"),
            ("manage", "Can manage this exam"),
            ("see_results", "Can see results of this exam"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def is_overall(self):
        """ Overall exam is automatically generated for common exam to store common statistics."""
        return bool(self.overall)

    def has_review_option(self):
        return bool(self.review_option)

    def has_amc_option(self):
        return bool(self.amc_option)

    def has_res_and_stats_option(self):
        return bool(self.res_and_stats_option)

    def has_prep_option(self):
        return bool(self.prep_option)

    def get_sum_common_students(self):
        """ Return the sum of all common students. """
        value = self.common_exams.all().filter(overall=False).aggregate(total=Count('students'))['total']
        return value

    def __str__(self):
        return self.code + "-" + self.name + " " + self.year.code + " " + str(self.semester.code)

    def get_max_points(self):
        """ Return the max points for an exam. """
        max_pts = 0
        for question in self.questions.all():
            max_pts += question.max_points

        return max_pts

    def get_common_points(self):
        """ Return the total of points for common part. """
        if self.overall:
            overall_exam = self
        else:
            overall_exam = self.common_exams.filter(overall=True).first()
        common_questions_list = list(overall_exam.questions.filter(removed_from_common=False).values_list("code", flat=True))
        common_pts = 0
        for question in self.questions.all():
            if question.code in common_questions_list:
                common_pts += question.max_points

        return common_pts

    def get_common_exams_yc_common(self):
        """ Return all common exams including the common (000-) """
        exam_list = [self]
        for comex in self.common_exams.all():
            exam_list.append(comex)

        return exam_list

    def get_common_exams_without_common(self):
        """ Return all common exams without the common (000-) """
        exam_list = Exam.objects.filter(common_exams=self,overall=False)
        for exam in exam_list.all():
            print( exam)
        return exam_list


    def get_students_results_exams(self):
        """ Return all exams for students results (without global one) """
        exam_list = []
        if not self.is_overall():
            exam_list.append(self)
        for comex in self.common_exams.all():
            exam_list.append(comex)
        return exam_list

    def get_available_common_exams(self):

        exam = self
        if self.is_overall():
            code_split = self.code.split('_')
            code = code_split[1]
            semester = self.semester
            year = self.year
            exam = Exam.objects.filter(code__startswith=code,semester=semester, year=year).exclude(code=self.code).first()

        available_exams = []
        if exam.questions.all():
            exam_code_search_start = exam.code.split('(')[0]
            code_split_end = exam.code.split(')')
            if len(code_split_end) > 1:
                exam_code_search_end = code_split_end[1]
                exams = Exam.objects.filter(code__startswith=exam_code_search_start, code__endswith=exam_code_search_end, year=exam.year, semester=exam.semester)
            else:
                exams = Exam.objects.filter(code__startswith=exam_code_search_start, year=exam.year, semester=exam.semester)

            common_exams = self.get_common_exams_yc_common()
            for exam in exams:
                if exam.questions.exists() and not exam in common_exams:
                    available_exams.append(exam)
        return available_exams



class QuestionType(models.Model):
    """ Stores question type data for questions """
    code = models.CharField(max_length=10,blank=False)
    name = models.CharField(max_length=100,blank=False)
    template = models.CharField(max_length=100,blank=True)
    formula = models.TextField(default='')
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.code} - {self.name}"

class Question(models.Model):
    """ Stores question data for an exam, related to :model:`examc_app.Exam` """
    code = models.CharField(max_length=50)
    common = models.BooleanField(default=0)
    # section = models.ForeignKey(ExamSection, on_delete=models.CASCADE,related_name='questions',blank=True,null=True)
    question_type = models.ForeignKey(QuestionType, on_delete=models.CASCADE,related_name='questions',blank=False,null=True)
    max_points = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    nb_answers = models.IntegerField(default=2)
    correct_answer = models.CharField(max_length=15,null=True)
    discriminatory_factor = models.IntegerField(default=0)
    upper_correct = models.IntegerField(default=0)
    lower_correct = models.IntegerField(default=0)
    di_calculation = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    tot_answers = models.IntegerField(default=0)
    remark = models.CharField(max_length=1000, blank=True,null=True)
    upper_avg = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    lower_avg = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField(blank=True,null=True,default='')
    formula = models.TextField(blank=True,null=True,default='')
    removed_from_common = models.BooleanField(default=False)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["exam", "code"], name="uniq_question_exam_code")
        ]

    def is_common(self):
        return bool(self.common)

    def __str__(self):
        return self.code

    def get_open_question_box_size(self):
        """ Return answer box size if open question from answer_text json """
        if self.question_type.code == 'OPEN':
            answer_box = QuestionAnswer.objects.filter(question=self, code='BOX').first()
            if answer_box:
                json_data = json.loads(answer_box.answer_text)
                return json_data["box_size"]

        return 0

    def get_open_question_box_type(self):
        """ Return answer box size if open question from answer_text json """
        if self.question_type.code == 'OPEN':
            answer_box = QuestionAnswer.objects.filter(question=self, code='BOX').first()
            if answer_box:
                json_data = json.loads(answer_box.answer_text)
                return json_data["box_type"]

        return '1'

class QuestionAnswer(models.Model):
    """ Stores question answer data for questions """
    code = models.CharField(max_length=10,blank=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE,related_name='answers',blank=False,null=True)
    answer_text = models.TextField(default='',blank=True,null=True)
    formula = models.TextField(default='', blank=True,null=True)
    is_correct = models.BooleanField(default=0)
    history = HistoricalRecords()

class ScoringStrategy(models.Model):
    """ Stores scoring strategy for an exam, questions and answers related to :model:`examc_app.Exam`:model:`examc_app.Question` :model:`examc_app.QuestionAnswer`  """
    max_points = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    inv_points = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    correct_choice_points = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    wrong_choice_points = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    no_answer_points = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    formula = models.TextField(default='')
    exam = models.OneToOneField(Exam, on_delete=models.CASCADE,related_name='scoring_strategy')
    question = models.OneToOneField(Question, on_delete=models.CASCADE,related_name='scoring_strategy')
    answer = models.OneToOneField(QuestionAnswer, on_delete=models.CASCADE,related_name='scoring_strategy')
    history = HistoricalRecords()

class Course(models.Model):
    """ Stores courses data, related to :model:`examc_app.Year` and :model:`examc_app.Semester` """
    code = models.CharField(max_length=20, blank=False)
    name = models.CharField(max_length=200, blank=False)
    semester = models.ForeignKey(Semester, on_delete=models.RESTRICT, related_name='courses')
    year = models.ForeignKey(AcademicYear, on_delete=models.RESTRICT, related_name='courses')
    teachers = models.CharField(max_length=500, blank=True)
