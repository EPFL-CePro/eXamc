########################
# RESULTS & STATISTICS
########################
from django.db import models
from simple_history.models import HistoricalRecords

from examc_app.models import Exam, Question


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

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["exam", "name"], name="uniq_scale_name_per_exam"),
        ]

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