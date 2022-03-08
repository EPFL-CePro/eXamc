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

    class Meta:
        unique_together = ('code','semester','year')
        ordering = ['-year', '-semester', 'code']

    def get_teachers(self):
        teachers = ''
        for user in self.users.all():
            if teachers:
                teachers += ', '
            teachers += user.last_name

    def __str__(self):
        return self.code + "-" + self.name + " " + self.year + " " + str(self.semester)
