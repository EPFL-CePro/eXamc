from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from examc_app.models import *


class SimpleTest(TestCase):
    def test_basic_addition(self):
        self.assertEqual(1 + 1, 2)


class ExAMCTest(TestCase):
    def setUp(self):
        self.pascal = User.objects.create_user('pascal', 'pascal@test.com', 'pascal')

        self.fo_exam = Exam.objects.create(name='Exam1', description='exam1 description')
        self.fo_exam.members.add(self.pascal)

    def test_dashboard_not_authenticated_user(self):
        url = reverse('examc_app:dashboard')
        response = self.client.get(url)
        self.assertTemplateNotUsed(response, 'examc_app/dashboard.html')
        self.failUnlessEqual(response.status_code, 302)