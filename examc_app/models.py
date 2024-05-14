from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from simple_history import register

# Get an instance of a logger
import logging

from django.db.models import Count

logger = logging.getLogger(__name__)

User.__str__ = lambda user_instance: user_instance.first_name + " " + user_instance.last_name

# history tracker for third-party model
register(User)


class Exam(models.Model):
    """
    Stores exam data, related to :model:`auth.User` and :model:`examc_app.Exam`
    """
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    semester = models.IntegerField(default=1)
    year = models.CharField(max_length=9)
    users = models.ManyToManyField(User, blank=True)
    present_students = models.IntegerField(default=0)
    common_exams = models.ManyToManyField("self", blank=True)
    overall = models.BooleanField(default=0)
    indiv_formula = models.CharField(max_length=100, blank=True)
    pages_by_copy = models.CharField(max_length=10000, blank=True)
    review_option = models.BooleanField(default=0)
    amc_option = models.BooleanField(default=0)
    res_and_stats_option = models.BooleanField(default=0)
    history = HistoricalRecords()

    class Meta:
        unique_together = ('code', 'semester', 'year')
        ordering = ['-year', '-semester', 'code']
        verbose_name = "Exam"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def is_overall(self):
        """ Overall exam is automatically generated for common exam to store common statistics."""
        return bool(self.overall)

    def has_review_option(self):
        """ Overall exam is automatically generated for common exam to store common statistics."""
        return bool(self.review_option)

    def has_amc_option(self):
        """ Overall exam is automatically generated for common exam to store common statistics."""
        return bool(self.amc_option)

    def has_res_and_stats_option(self):
        """ Overall exam is automatically generated for common exam to store common statistics."""
        return bool(self.res_and_stats_option)

    def get_sum_common_students(self):
        """ Return the sum of all common students. """
        value = self.common_exams.all().filter(overall=False).aggregate(total=Count('students'))['total']
        return value

    # def get_teachers(self):
    #     teachers = ''
    #     for user in self.users.all():
    #         if teachers:
    #             teachers += ', '
    #         teachers += user.last_name

    def __str__(self):
        return self.code + "-" + self.name + " " + self.year + " " + str(self.semester)

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


############
# REVIEW
############
class PagesGroup(models.Model):
    """ Stores pages group data, representing pages for questions, related to :model:`examc_app.Exam` """
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='pagesGroup')
    group_name = models.CharField(max_length=20, default='0')
    page_from = models.IntegerField(default=0)
    page_to = models.IntegerField(default=0)
    grading_help = models.TextField(default='')
    rectangle = models.TextField(default='')
    correctorBoxes = models.TextField(blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.group_name + " ( pages " + str(self.page_from) + "..." + str(self.page_to) + " )"


class Reviewer(models.Model):
    """ Stores reviewer for exam data, related to :model:`examc_app.Exam`, :model:`examc_app.PagesGroup` and :model:`auth.User` """
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='reviewers')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviewers')
    pages_groups = models.ManyToManyField(PagesGroup, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.exam.code + " - " + self.user.username


class PagesGroupComment(models.Model):
    """ Stores comments data for group of pages for an exam copy, related to :model:`examc_app.Exam`, :model:`examc_app.PagesGroup`, :model:`examc_app.PagesGroupComment` and :model:`auth.User` """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pagesGroupComments')
    pages_group = models.ForeignKey(PagesGroup, on_delete=models.CASCADE, related_name='pagesGroupComments', blank=True)
    copy_no = models.CharField(max_length=10, default='0')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, default=None, null=True)
    created = models.DateTimeField(auto_now_add=True, blank=True)
    modified = models.DateTimeField(blank=True, null=True)
    content = models.TextField()
    is_new = models.BooleanField()
    history = HistoricalRecords()

    def serialize(self, curr_user_id):
        """ Serialize the comment data """
        modified_str = ""
        if self.modified:
            modified_str = self.modified.strftime("%Y-%m-%d %H:%M:%S")
        profile_picture = 'far fa-user-circle fa-sm'
        if self.user_id == curr_user_id:
            profile_picture = 'fa fa-user-circle fa-sm'
        return {
            "id": self.pk,
            "parent": self.parent_id,
            "created": self.created.strftime("%Y-%m-%d %H:%M:%S"),
            "modified": modified_str,
            "content": self.content,
            "creator": self.user_id,
            "fullname": self.user.first_name + " " + self.user.last_name,
            "is_new": self.is_new,
            "profile_picture_url": profile_picture
        }


class PageMarkers(models.Model):
    """ Stores markers data for a scan page, related to :model:`examc_app.Exam`, :model:`examc_app.PagesGroup`, :model:`examc_app.PagesGroupComment` """
    copie_no = models.CharField(max_length=10, default='0')
    page_no = models.CharField(max_length=10, default='0')
    pages_group = models.ForeignKey(PagesGroup, on_delete=models.CASCADE, related_name='pageMarkers', blank=True,
                                    null=True)
    filename = models.CharField(max_length=100)
    markers = models.TextField(blank=True)
    comment = models.TextField(blank=True)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='pageMarkers')
    correctorBoxMarked = models.BooleanField(default=False)
    history = HistoricalRecords()

    def __str__(self):
        return self.copie_no + " - " + self.filename + " " + self.exam.code


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
                self.final) + ")" + self.exam.code + " - " + self.exam.name + " " + self.exam.year + " " + str(
                self.exam.semester)
        else:
            return self.name + "(" + str(self.total_points) + ", " + str(
                self.points_to_add) + ", " + self.formula + ", " + str(self.final) + ") NO EXAM !"


class Question(models.Model):
    """ Stores question data for an exam, related to :model:`examc_app.Exam` """
    code = models.CharField(max_length=50)
    common = models.BooleanField(default=0)
    qtype = models.IntegerField(default=1)
    max_points = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    answers = models.IntegerField(default=2)
    correct_answer = models.CharField(max_length=15)
    discriminatory_factor = models.IntegerField(default=0)
    upper_correct = models.IntegerField(default=0)
    lower_correct = models.IntegerField(default=0)
    di_calculation = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    tot_answers = models.IntegerField(default=0)
    remark = models.CharField(max_length=1000, default='')
    upper_avg = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    lower_avg = models.DecimalField(max_digits=10, decimal_places=5, default=0.0)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    history = HistoricalRecords()

    def is_common(self):
        return bool(self.common)

    def __str__(self):
        return self.code


class Student(models.Model):
    """ Stores student data for an exam, related to :model:`examc_app.Exam` """
    copie_no = models.CharField(max_length=10, default='0')
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
