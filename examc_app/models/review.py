############
# REVIEW
############
from django.contrib.auth.models import Group, User
from django.db import models
from simple_history.models import HistoricalRecords

from examc_app.models import Exam, Student


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
    description = models.TextField(blank=True, default="")
    adjustment = models.BooleanField(default=0)
    position = models.IntegerField(default=0)
    history = HistoricalRecords()

    class Meta:
        ordering = ['position']

#############################
# Review Grading Schemes Checked Boxes
#############################
class PagesGroupGradingSchemeCheckedBox(models.Model):
    pages_group = models.ForeignKey(PagesGroup, on_delete=models.CASCADE, related_name='pagesGroupGradingSchemeCheckedBoxes')
    gradingSchemeCheckBox = models.ForeignKey(QuestionGradingSchemeCheckBox, on_delete=models.CASCADE, related_name='pagesGroupGradingSchemeCheckedBoxes', null=True)
    copy_nr = models.CharField(max_length=10, default='0')
    adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    history = HistoricalRecords()

class ReviewLock(models.Model):
    pages_group = models.ForeignKey(PagesGroup, on_delete=models.CASCADE, related_name='reviewLocks')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='reviewLocks')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviewLocks')


