from multiprocessing.connection import Client

from django.test import TestCase
from django_tequila.django_backend import User


class ViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user()
        self.client

