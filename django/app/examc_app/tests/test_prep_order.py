from django.test import TestCase
from django.urls import reverse

from examc_app.models import PrepStudent
from examc_app.services.student.prep_order import StudentsOrderError, move_prep_student, reorder_prep_students
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user

# copy_no, sciper, last name, first name, section, room, seat
STUDENTS = [
    (1, 400000, "Zuse", "Konrad", "IN", "CO 1", "R1-10"),
    (2, 300000, "Émery", "Alice", None, "CO 1", "R1-2"),
    (3, 200000, "", "", "MX", None, ""),
    (4, 100000, "Babbage", "Charles", "IN", "BC 01", "A1"),
]


class ReorderPrepStudentsTestCase(TestCase):
    def setUp(self):
        self.exam = create_mock_exam()
        for copy_no, sciper, last_name, first_name, section, room, seat in STUDENTS:
            PrepStudent.objects.create(exam=self.exam, copy_no=copy_no, sciper=sciper, last_name=last_name,
                                       first_name=first_name, section=section, room=room, seat=seat,
                                       needs_correction=not last_name)
        self.other = PrepStudent.objects.create(exam=create_mock_exam(code="OTHER"), copy_no=1, sciper=999999,
                                                first_name="F", last_name="Other", seat="")

    def scipers(self):
        return list(self.exam.prepStudents.order_by("copy_no").values_list("sciper", flat=True))

    def test_orders(self):
        expected = {
            # Accents ignored, students without names last
            "name": [100000, 300000, 400000, 200000],
            "sciper": [100000, 200000, 300000, 400000],
            # Without section last
            "section": [100000, 400000, 200000, 300000],
            # Rooms then seats compared with their numbers: R1-2 before R1-10, no room last
            "seat": [100000, 300000, 400000, 200000],
        }
        for order, scipers in expected.items():
            with self.subTest(order=order):
                self.assertEqual(reorder_prep_students(self.exam, order), 4)
                self.assertEqual(self.scipers(), scipers)
                self.assertEqual(sorted(self.exam.prepStudents.values_list("copy_no", flat=True)), [1, 2, 3, 4])

        self.other.refresh_from_db()
        self.assertEqual(self.other.copy_no, 1)

    def test_random_keeps_rooms_and_seats(self):
        seats = dict(self.exam.prepStudents.values_list("sciper", "seat"))

        reorder_prep_students(self.exam, "random")

        self.assertEqual(sorted(self.scipers()), [100000, 200000, 300000, 400000])
        self.assertEqual(dict(self.exam.prepStudents.values_list("sciper", "seat")), seats)

    def test_unknown_order(self):
        with self.assertRaises(StudentsOrderError):
            reorder_prep_students(self.exam, "seat; DROP")

    def test_move(self):
        move_prep_student(PrepStudent.objects.get(sciper=100000), 1)
        self.assertEqual(self.scipers(), [100000, 400000, 300000, 200000])

        move_prep_student(PrepStudent.objects.get(sciper=100000), 3)
        self.assertEqual(self.scipers(), [400000, 300000, 100000, 200000])

        with self.assertRaisesMessage(StudentsOrderError, "from 1 to 4"):
            move_prep_student(PrepStudent.objects.get(sciper=100000), 5)


class ReorderViewsTestCase(TestCase):
    def setUp(self):
        self.exam = create_mock_exam()
        for copy_no, sciper, last_name in ((1, 200000, "Zuse"), (2, 100000, "Babbage")):
            PrepStudent.objects.create(exam=self.exam, copy_no=copy_no, sciper=sciper, first_name="F",
                                       last_name=last_name, seat="")
        user = create_mock_user()
        user.is_superuser = True
        user.save()
        self.client.force_login(user)

    def test_reorder(self):
        url = reverse("reorder_prep_students", kwargs={"exam_pk": self.exam.pk})

        self.assertEqual(self.client.post(url, {"order": "name"}).json(), {"reordered": 2})
        self.assertEqual(PrepStudent.objects.get(sciper=100000).copy_no, 1)
        self.assertEqual(self.client.post(url, {"order": "other"}).status_code, 400)

        self.exam.is_finalized = True
        self.exam.save()
        self.assertEqual(self.client.post(url, {"order": "sciper"}).status_code, 403)

    def test_move_with_the_edit_api(self):
        student = PrepStudent.objects.get(sciper=100000)
        url = reverse("api-exam-prep-students-detail", kwargs={"exam_pk": self.exam.pk, "pk": student.pk})

        response = self.client.patch(url, {"copy_no": 1, "seat": "A1"}, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(self.exam.prepStudents.order_by("copy_no").values_list("sciper", "seat")),
                         [(100000, "A1"), (200000, "")])
        response = self.client.patch(url, {"copy_no": 3}, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PrepStudent.objects.get(sciper=100000).copy_no, 1)
