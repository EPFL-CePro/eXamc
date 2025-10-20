import json
# Get an instance of a logger
import logging

from django.contrib.auth.models import User, Group
from django.db import models
from django.db.models import Count
from django.utils import timezone
from django_ckeditor_5.fields import CKEditor5Field
# from simple_history import register
from simple_history.models import HistoricalRecords

logger = logging.getLogger(__name__)

User.__str__ = lambda user_instance: user_instance.first_name + " " + user_instance.last_name

# # history tracker for third-party model
# register(User)



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
    first_page_text = CKEditor5Field('Text', config_name='extends',default='',null=True,blank=True)#models.TextField(default='')
    review_option = models.BooleanField(default=0)
    amc_option = models.BooleanField(default=0)
    res_and_stats_option = models.BooleanField(default=0)
    prep_option = models.BooleanField(default=0)
    history = HistoricalRecords()
    pdf_catalog_name = models.CharField(max_length=200, blank=True,null=True)

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
        common_pts = 0
        for question in self.questions.all():
            if question.common:
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
            code_split = self.code.split('-')
            name = code_split[1]
            semester = Semester.objects.get(code=code_split[4])
            year = AcademicYear.objects.get(code=code_split[2]+"-"+code_split[3])
            exam = Exam.objects.filter(name__startswith=name,semester=semester, year=year).exclude(code=self.code).first()

        exam_code_search_start = exam.code.split('(')[0]
        code_split_end = exam.code.split(')')
        if len(code_split_end) > 1:
            exam_code_search_end = code_split_end[1]
            exams = Exam.objects.filter(code__startswith=exam_code_search_start, code__endswith=exam_code_search_end, year=exam.year, semester=exam.semester)
        else:
            exams = Exam.objects.filter(code__startswith=exam_code_search_start, year=exam.year, semester=exam.semester)
        available_exams = []
        common_exams = self.get_common_exams_yc_common()
        for exam in exams:
            if not exam in common_exams:
                available_exams.append(exam)
        return available_exams

class ExamSection(models.Model):
    """ Stores section data for an exam, related to :model:`examc_app.Exam` """
    section_number = models.IntegerField(blank=False,null=True)
    title = models.CharField(max_length=200,blank=False, null=True, default='')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE,related_name='sections',blank=False)
    header_text = models.TextField(default='')
    history = HistoricalRecords()

class QuestionType(models.Model):
    """ Stores question type data for questions """
    code = models.CharField(max_length=10,blank=False)
    name = models.CharField(max_length=100,blank=False)
    template = models.CharField(max_length=100,blank=True)
    formula = models.TextField(default='')
    history = HistoricalRecords()

class Question(models.Model):
    """ Stores question data for an exam, related to :model:`examc_app.Exam` """
    code = models.CharField(max_length=50)
    common = models.BooleanField(default=0)
    section = models.ForeignKey(ExamSection, on_delete=models.CASCADE,related_name='questions',blank=True,null=True)
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
    history = HistoricalRecords()

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


############
# REVIEW
############
class PagesGroup(models.Model):
    """ Stores pages group data, representing pages for questions, related to :model:`examc_app.Exam` """
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='pagesGroup')
    group_name = models.CharField(max_length=50, default='0')
    nb_pages = models.IntegerField(default=0)
    grading_help = models.TextField(default='')
    use_grading_scheme = models.BooleanField(default=False)
    history = HistoricalRecords()

    def __str__(self):
        return self.group_name + " ( pages " + str(self.nb_pages) + " )"

class ExamUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,related_name='user_exams')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE,related_name='exam_users')
    group = models.ForeignKey(Group, on_delete=models.CASCADE,related_name='user_groups', null=True,default=None)
    pages_groups = models.ManyToManyField(PagesGroup, blank=True)
    review_blocked = models.BooleanField(default=False)
    history = HistoricalRecords()


class PagesGroupComment(models.Model):
    """ Stores comments data for group of pages for an exam copy, related to :model:`examc_app.Exam`, :model:`examc_app.PagesGroup`, :model:`examc_app.PagesGroupComment` and :model:`auth.User` """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pagesGroupComments')
    pages_group = models.ForeignKey(PagesGroup, on_delete=models.CASCADE, related_name='pagesGroupComments', blank=True)
    copy_no = models.CharField(max_length=10, default='0')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, default=None, null=True, related_name='children')
    created = models.DateTimeField(auto_now_add=True, blank=True)
    modified = models.DateTimeField(blank=True, null=True)
    content = models.TextField()
    is_new = models.BooleanField(default=False)
    history = HistoricalRecords()

    def serialize(self, curr_user_id):
        """ Serialize the comment data """
        modified_str = ""
        if self.modified:
            modified_str = self.modified.strftime("%Y-%m-%d %H:%M:%S")
        profile_picture = 'fa-regular fa-circle-user fa-2xs'
        created_by_curr_user = False
        if self.user_id == curr_user_id:
            profile_picture = 'fa-solid fa-circle-user fa-2xs'
            created_by_curr_user = True
        return {
            "id": self.pk,
            "parent": self.parent_id,
            "created": self.created.strftime("%Y-%m-%d %H:%M:%S"),
            "modified": modified_str,
            "content": self.content,
            "creator": self.user_id,
            "fullname": self.user.first_name + " " + self.user.last_name,
            "is_new": self.is_new,
            "profile_picture_url": profile_picture,
            "created_by_current_user": created_by_curr_user
        }


class PageMarkers(models.Model):
    """ Stores markers data for a scan page, related to :model:`examc_app.Exam`, :model:`examc_app.PagesGroup`, :model:`examc_app.PagesGroupComment` """
    copie_no = models.CharField(max_length=10, default='',blank=True)
    page_no = models.CharField(max_length=10, default='')
    pages_group = models.ForeignKey(PagesGroup, on_delete=models.CASCADE, related_name='pageMarkers', blank=True,
                                    null=True)
    filename = models.CharField(max_length=100)
    markers = models.TextField(blank=True)
    #comment = models.TextField(blank=True)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='pageMarkers')
    correctorBoxMarked = models.BooleanField(default=False)
    history = HistoricalRecords()

    def __str__(self):
        return self.copie_no + " - " + self.filename + " " + self.exam.code

    def get_users_with_date(self):
        users_list = []
        for pm_user in self.pageMarkers_users.all():
            user_dict = {}
            user_dict["username"]=pm_user.user.username
            user_dict["date"]=pm_user.modified.strftime("%Y-%m-%d %H:%M:%S")
            users_list.append(user_dict)

        return users_list

class PageMarkersUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,related_name='user_pageMarkers')
    pageMarkers = models.ForeignKey(PageMarkers, on_delete=models.CASCADE,related_name='pageMarkers_users')
    created = models.DateTimeField(auto_now_add=True, blank=True)
    modified = models.DateTimeField(blank=True, null=True)

########################
# RESULTS & STATISTICS
########################
class Scale(models.Model):
    """ Stores scale data for an exam, related to :model:`examc_app.Exam` """
    name = models.CharField(max_length=20)
    total_points = models.DecimalField(max_digits=6, decimal_places=2)
    points_to_add = models.DecimalField(max_digits=6, decimal_places=2, default=0.0)
    min_grade = models.DecimalField(max_digits=6, decimal_places=2, default=1.0)
    max_grade = models.DecimalField(max_digits=6, decimal_places=2, default=6.0)
    rounding = models.IntegerField(choices=((1, "1/4"), (2, "1/2"), (3, "None")), default=1)
    formula = models.CharField(max_length=250, blank=True)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='scales', null=True)
    final = models.BooleanField(default=0)
    history = HistoricalRecords()

    def __str__(self):
        if self.exam:
            return self.name + "(" + str(self.total_points) + ", " + str(
                self.points_to_add) + ", " + self.formula + ", " + str(
                self.final) + ")" + self.exam.code + " - " + self.exam.name + " " + self.exam.year.code + " " + str(
                self.exam.semester)
        else:
            return self.name + "(" + str(self.total_points) + ", " + str(
                self.points_to_add) + ", " + self.formula + ", " + str(self.final) + ") NO EXAM !"


class Student(models.Model):
    """ Stores student data for an exam, related to :model:`examc_app.Exam` """
    copie_no = models.CharField(max_length=10, default='0')
    amc_id = models.CharField(max_length=10, default='0')
    sciper = models.CharField(max_length=10, default='999999')
    name = models.CharField(max_length=100)
    section = models.CharField(max_length=20)
    points = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    present = models.BooleanField(default=0)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='students')
    history = HistoricalRecords()

    def __str__(self):
        return self.copie_no + " - " + self.sciper + " " + self.name


### Student Exam Data
class StudentQuestionAnswer(models.Model):
    """ Stores student question answer for an exam, related to :model:`examc_app.Exam` and :model:`examc_app.Question` """
    ticked = models.CharField(max_length=20, null=True)
    points = models.DecimalField(max_digits=14, decimal_places=10, default=0.0)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='questionAnswers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='questionAnswers')
    history = HistoricalRecords()


### Statistics
class ScaleStatistic(models.Model):
    """ Stores scale statistic data for an exam, related to :model:`examc_app.Exam` and :model:`examc_app.Scale` """
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='scaleStatistics')
    scale = models.ForeignKey(Scale, on_delete=models.CASCADE, related_name='scaleStatistics')
    average = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    stddev = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    median = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    color = models.CharField(max_length=20, default='lightblue')
    section = models.CharField(max_length=10, default='')
    section_nb_students = models.IntegerField(default=0)
    section_presents = models.IntegerField(default=0)
    history = HistoricalRecords()


class AnswerStatistic(models.Model):
    """ Stores answers statistic data for a question, related to :model:`examc_app.Question` """
    answer = models.CharField(max_length=15, default='')
    quantity = models.IntegerField(default=1)
    rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answerStatistics')
    history = HistoricalRecords()


class StudentScaleGrade(models.Model):
    """ Stores student grade for a scale, related to :model:`examc_app.Student` and :model:`examc_app.Scale` """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='scaleGrades')
    scale = models.ForeignKey(Scale, on_delete=models.CASCADE, related_name='scaleGrades')
    grade = models.DecimalField(max_digits=4, decimal_places=2, default=0.0)
    history = HistoricalRecords()


class ScaleDistribution(models.Model):
    """ Stores exam distribution data for a scale, related to :model:`examc_app.ScaleStatistic` """
    scale_statistic = models.ForeignKey(ScaleStatistic, on_delete=models.CASCADE, related_name='scaleDistributions')
    grade = models.DecimalField(max_digits=4, decimal_places=2, default=0.0)
    quantity = models.IntegerField(default=1)
    history = HistoricalRecords()

    class Meta:
        ordering = ['grade']


class ComVsIndStatistic(models.Model):
    """ Stores common vs individual statistic data for an exam and scale, related to :model:`examc_app.Exam` and :model:`examc_app.Scale` """
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='comVsIndStatistics')
    section = models.CharField(max_length=10, default='')
    scale = models.ForeignKey(Scale, on_delete=models.CASCADE, related_name='comVsIndStatistics')
    glob_avg_grade = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    com_rate = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    com_avg_pts = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    com_avg_grade = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    ind_avg_pts = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    ind_avg_grade = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    history = HistoricalRecords()

class Course(models.Model):
    """ Stores courses data, related to :model:`examc_app.Year` and :model:`examc_app.Semester` """
    code = models.CharField(max_length=20, blank=False)
    name = models.CharField(max_length=200, blank=False)
    semester = models.ForeignKey(Semester, on_delete=models.RESTRICT, related_name='courses')
    year = models.ForeignKey(AcademicYear, on_delete=models.RESTRICT, related_name='courses')
    teachers = models.CharField(max_length=500, blank=True)

class ReviewLock(models.Model):
    pages_group = models.ForeignKey(PagesGroup, on_delete=models.CASCADE, related_name='reviewLocks')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='reviewLocks')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviewLocks')


###########################
# Grading Schemes
###########################
class QuestionGradingScheme(models.Model):
    pages_group = models.ForeignKey(PagesGroup, on_delete=models.CASCADE, related_name='gradingSchemes')
    name = models.CharField(max_length=100)
    max_points = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    description = models.TextField(default='')
    history = HistoricalRecords()

class QuestionGradingSchemeCheckBox(models.Model):
    questionGradingScheme = models.ForeignKey(QuestionGradingScheme, on_delete=models.CASCADE, related_name='checkboxes')
    name = models.CharField(max_length=100)
    points = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    description = models.TextField(default='')
    history = HistoricalRecords()

#############################
# Review Grading Schemes Checked Boxes
#############################
class PagesGroupGradingSchemeCheckedBox(models.Model):
    pages_group = models.ForeignKey(PagesGroup, on_delete=models.CASCADE, related_name='pagesGroupGradingSchemeCheckedBoxes')
    gradingSchemeCheckBox = models.ForeignKey(QuestionGradingSchemeCheckBox, on_delete=models.CASCADE, related_name='pagesGroupGradingSchemeCheckedBoxes', null=True)
    copy_nr = models.CharField(max_length=10, default='0')
    adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    history = HistoricalRecords()


#############################
# AMC MODELS
#############################

# ### LAYOUT
#
# class LayoutVariables(models.Model):
#     """
#     Corresponds to table layout_variables:
#       name TEXT UNIQUE
#       value TEXT
#     """
#     name = models.CharField(max_length=255, unique=True)
#     value = models.CharField(max_length=255)
#
# class LayoutMark(models.Model):
#     """
#     Corresponds to table layout_mark:
#       student INTEGER
#       page INTEGER
#       corner INTEGER
#       x REAL
#       y REAL
#       PRIMARY KEY (student,page,corner)
#     Again, emulate with unique_together.
#     """
#     student = models.IntegerField()
#     page = models.IntegerField()
#     corner = models.IntegerField()
#     x = models.FloatField()
#     y = models.FloatField()
#
#     class Meta:
#         unique_together = (('student', 'page', 'corner'),)
#
#
# class LayoutBox(models.Model):
#     """
#     Corresponds to table layout_box:
#       student INTEGER
#       page INTEGER
#       role INTEGER DEFAULT 1
#       question INTEGER
#       answer INTEGER
#       xmin REAL
#       xmax REAL
#       ymin REAL
#       ymax REAL
#       flags INTEGER DEFAULT 0
#       char TEXT
#       PRIMARY KEY (student, role, question, answer)
#       Index: layout_index_box_studentpage ON (student, page, role)
#     """
#     student = models.IntegerField()
#     page = models.IntegerField()
#     role = models.IntegerField(default=1)
#     question = models.IntegerField()
#     answer = models.IntegerField()
#     xmin = models.FloatField(null=True, blank=True)
#     xmax = models.FloatField(null=True, blank=True)
#     ymin = models.FloatField(null=True, blank=True)
#     ymax = models.FloatField(null=True, blank=True)
#     flags = models.IntegerField(default=0)
#     char = models.CharField(max_length=255, blank=True, null=True)
#
#     class Meta:
#         unique_together = (('student', 'role', 'question', 'answer'),)
#         indexes = [
#             models.Index(fields=['student', 'page', 'role'],
#                          name='layout_index_box_studentpage'),
#         ]
#
#
# class LayoutDigit(models.Model):
#     """
#     Corresponds to table layout_digit:
#       student INTEGER
#       page INTEGER
#       numberid INTEGER
#       digitid INTEGER
#       xmin REAL
#       xmax REAL
#       ymin REAL
#       ymax REAL
#       PRIMARY KEY (student,page,numberid,digitid)
#     """
#     student = models.IntegerField()
#     page = models.IntegerField()
#     numberid = models.IntegerField()
#     digitid = models.IntegerField()
#     xmin = models.FloatField(null=True, blank=True)
#     xmax = models.FloatField(null=True, blank=True)
#     ymin = models.FloatField(null=True, blank=True)
#     ymax = models.FloatField(null=True, blank=True)
#
#     class Meta:
#         unique_together = (('student', 'page', 'numberid', 'digitid'),)
#
# class LayoutPage(models.Model):
#     """
#     Corresponds to table layout_page:
#       student INTEGER
#       page INTEGER
#       checksum INTEGER
#       sourceid INTEGER
#       subjectpage INTEGER
#       dpi REAL
#       width REAL
#       height REAL
#       markdiameter REAL
#       PRIMARY KEY (student,page)
#     We emulate the primary key using unique_together below.
#     """
#     student = models.IntegerField()
#     page = models.IntegerField()
#     checksum = models.IntegerField(null=True, blank=True)
#     subjectpage = models.IntegerField(null=True, blank=True)
#     dpi = models.FloatField(null=True, blank=True)
#     width = models.FloatField(null=True, blank=True)
#     height = models.FloatField(null=True, blank=True)
#     markdiameter = models.FloatField(null=True, blank=True)
#
#     class Meta:
#         unique_together = (('student', 'page'),)
#
# class LayoutQuestion(models.Model):
#     """
#     Corresponds to table layout_question:
#       question INTEGER PRIMARY KEY
#       name TEXT
#     We'll use question as the primary key.
#     """
#     question = models.IntegerField(primary_key=True)
#     name = models.CharField(max_length=255, blank=True,null=True)
#
#
# class LayoutAssociation(models.Model):
#     """
#     Corresponds to table layout_association:
#       student INTEGER PRIMARY KEY
#       id TEXT
#       filename TEXT
#     'id' conflicts with Django's auto 'id', so rename to association_id.
#     We keep 'student' as the primary_key, matching the SQL schema.
#     """
#     student = models.IntegerField(primary_key=True)
#     association_id = models.TextField(db_column='id', null=True, blank=True)
#     filename = models.CharField(max_length=255, blank=True,null=True)
#
#
# class LayoutChar(models.Model):
#     """
#     Corresponds to table layout_char:
#       question INTEGER
#       answer INTEGER
#       char TEXT
#       Unique index on (question, answer)
#     """
#     question = models.IntegerField()
#     answer = models.IntegerField()
#     char = models.CharField(max_length=255, blank=True,null=True)
#
#     class Meta:
#         unique_together = (('question', 'answer'),)
#
#
# class LayoutZone(models.Model):
#     """
#     Corresponds to table layout_zone:
#       student INTEGER
#       page INTEGER
#       zone TEXT
#       flags INTEGER DEFAULT 0
#       xmin REAL
#       xmax REAL
#       ymin REAL
#       ymax REAL
#       Index: layout_index_zone ON (student,page)
#     There is no PRIMARY KEY definition. By default, Django adds its own 'id'.
#     """
#     student = models.IntegerField()
#     page = models.IntegerField()
#     zone = models.CharField(max_length=255, blank=True,null=True)
#     flags = models.IntegerField(default=0)
#     xmin = models.FloatField(null=True, blank=True)
#     xmax = models.FloatField(null=True, blank=True)
#     ymin = models.FloatField(null=True, blank=True)
#     ymax = models.FloatField(null=True, blank=True)
#
#     class Meta:
#         indexes = [
#             models.Index(fields=['student', 'page'], name='layout_index_zone'),
#         ]

