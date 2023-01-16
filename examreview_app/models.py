from django.db import models
from django.contrib.auth.models import User

# Get an instance of a logger
import logging
logger = logging.getLogger(__name__)

class Exam(models.Model):
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    semester = models.IntegerField(default=1)
    year = models.CharField(max_length=9)
    users = models.ManyToManyField(User, blank=True)
    present_students = models.IntegerField(default=0)
    common_exams = models.ManyToManyField("self", blank=True)
    pdf_catalog_name = models.CharField(max_length=100, blank=True)
    overall = models.BooleanField(default=0)
    indiv_formula = models.CharField(max_length=100, blank=True)
    pages_by_copy = models.IntegerField(default=0)

    class Meta:
        unique_together = ('code','semester','year')
        ordering = ['-year', '-semester', 'code']

    def is_overall(self):
        return bool(self.overall)

    def get_sum_common_students(self):
        value = self.common_exams.all().filter(overall=False).aggregate(total=Count('students'))['total']
        return value

    def get_teachers(self):
        teachers = ''
        for user in self.users.all():
            if teachers:
                teachers += ', '
            teachers += user.last_name

    def __str__(self):
        return self.code + "-" + self.name + " " + self.year + " " + str(self.semester)

    def get_max_points(self):
        max_pts = 0
        for question in self.questions.all():
            max_pts += question.max_points

        return max_pts

    def get_common_points(self):
        common_pts = 0
        for question in self.questions.all():
            if question.common:
                common_pts += question.max_points

        return common_pts

class ExamPagesGroup(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='examPagesGroup')
    group_name = models.CharField(max_length=20,default='0')
    page_from = models.IntegerField(default=0)
    page_to = models.IntegerField(default=0)
 
    def __str__(self):
        return self.exam.code + " - " + self.group_name + " " + str(self.page_from) + "..." + str(self.page_to)

class ScanMarkers(models.Model):
    copie_no = models.CharField(max_length=10,default='0')
    filename = models.CharField(max_length=100)
    markers = models.TextField(blank = True)
    comment = models.TextField(blank = True)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='scanMarkers')

    def __str__(self):
        return self.copie_no + " - " + self.filename + " " + self.exam.code
