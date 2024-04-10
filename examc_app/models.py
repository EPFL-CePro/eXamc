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
    pages_by_copy = models.CharField(max_length=10000, blank=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = ('code', 'semester', 'year')
        ordering = ['-year', '-semester', 'code']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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

    # def get_max_points(self):
    #     max_pts = 0
    #     for question in self.questions.all():
    #         max_pts += question.max_points
    #
    #     return max_pts

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
    grading_help = models.TextField(default='')
    correctorBoxes = models.TextField(blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.group_name + " ( pages " + str(self.page_from) + "..." + str(self.page_to) + " )"

class ExamReviewer(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='examReviewers')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='examReviewers')
    pages_groups = models.ManyToManyField(ExamPagesGroup, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.exam.code + " - " + self.user.username


class ExamPagesGroupComment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='examPagesGroupComments')
    pages_group = models.ForeignKey(ExamPagesGroup, on_delete=models.CASCADE, related_name='examPagesGroupComments', blank=True)
    copy_no = models.CharField(max_length=10, default='0')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, default=None, null=True)
    created = models.DateTimeField(auto_now_add=True, blank=True)
    modified = models.DateTimeField(blank=True, null=True)
    content = models.TextField()
    is_new = models.BooleanField()
    history = HistoricalRecords()

    def serialize(self, curr_user_id):
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
            "fullname": self.user.first_name+" "+self.user.last_name,
            "is_new": self.is_new,
            "profile_picture_url": profile_picture
        }


class ScanMarkers(models.Model):
    copie_no = models.CharField(max_length=10,default='0')
    page_no = models.CharField(max_length=10,default='0')
    pages_group = models.ForeignKey(ExamPagesGroup, on_delete=models.CASCADE, related_name='examPagesGroupMarkers', blank=True,null=True)
    filename = models.CharField(max_length=100)
    markers = models.TextField(blank = True)
    comment = models.TextField(blank = True)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='scanMarkers')
    correctorBoxMarked = models.BooleanField(default=False)
    history = HistoricalRecords()


    def __str__(self):
        return self.copie_no + " - " + self.filename + " " + self.exam.code


class DrawnImage(models.Model):
    image_data = models.IntegerField(default=False)
    group_id = models.IntegerField(default=False)

    def __str__(self):
        return f'Image (ID: {self.id})'

