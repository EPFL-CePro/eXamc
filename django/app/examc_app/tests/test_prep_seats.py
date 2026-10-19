from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from examc_app.models import PrepStudent
from examc_app.services.student.prep_seats import (
    SeatsAssignmentError, assign_rooms_and_seats, check_seat_pattern, format_seat,
)
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user


class FormatSeatTestCase(SimpleTestCase):
    def test_leading_zeros_up_to_the_number_of_hashes(self):
        self.assertEqual([format_seat("R1-##", n) for n in (1, 50, 100)], ["R1-01", "R1-50", "R1-100"])
        self.assertEqual(format_seat("#", 7), "7")
        self.assertEqual(format_seat("A###B", 12), "A012B")

    def test_pattern_needs_one_group_of_hashes(self):
        self.assertIsNone(check_seat_pattern("R1-##"))
        self.assertIn("no '#'", check_seat_pattern("R1"))
        self.assertIn("only one group", check_seat_pattern("R#-##"))


class AssignRoomsAndSeatsTestCase(TestCase):
    def setUp(self):
        self.exam = create_mock_exam()
        for copy_no in (3, 1, 2, 4):
            PrepStudent.objects.create(exam=self.exam, copy_no=copy_no, sciper=100000 + copy_no, first_name="F",
                                       last_name=f"L{copy_no}", room="OLD", seat=f"S{copy_no}")
        PrepStudent.objects.create(exam=create_mock_exam(code="OTHER"), copy_no=2, sciper=999999, first_name="F",
                                   last_name="Other", room="KEEP", seat="KEEP")

    def rooms_and_seats(self, exam=None):
        return list((exam or self.exam).prepStudents.order_by("copy_no").values_list("copy_no", "room", "seat"))

    def test_range_in_id_order(self):
        result = assign_rooms_and_seats(self.exam, 2, 3, room="CO 1", seat_pattern="R1-##", first_number=9)

        self.assertEqual((result.updated, result.first_seat, result.last_seat), (2, "R1-09", "R1-10"))
        self.assertEqual(self.rooms_and_seats(), [
            (1, "OLD", "S1"), (2, "CO 1", "R1-09"), (3, "CO 1", "R1-10"), (4, "OLD", "S4"),
        ])
        self.assertEqual(PrepStudent.objects.get(sciper=999999).seat, "KEEP")
        self.assertEqual(PrepStudent.history.filter(exam_id=self.exam.pk, history_type="~").count(), 2)

    def test_empty_room_or_pattern_keeps_the_current_values(self):
        assign_rooms_and_seats(self.exam, 1, 2, room="CO 1")
        assign_rooms_and_seats(self.exam, 3, 4, seat_pattern="#")

        self.assertEqual(self.rooms_and_seats(), [
            (1, "CO 1", "S1"), (2, "CO 1", "S2"), (3, "OLD", "1"), (4, "OLD", "2"),
        ])

    def test_all_problems_reported_and_nothing_changed(self):
        before = self.rooms_and_seats()
        with self.assertRaises(SeatsAssignmentError) as raised:
            assign_rooms_and_seats(self.exam, 3, 2, seat_pattern="R1", first_number=-1)
        self.assertEqual(len(raised.exception.errors), 3)

        with self.assertRaises(SeatsAssignmentError):
            assign_rooms_and_seats(self.exam, 1, 4)
        with self.assertRaisesMessage(SeatsAssignmentError, "No student has an ID from 10 to 20"):
            assign_rooms_and_seats(self.exam, 10, 20, room="CO 1")
        self.assertEqual(self.rooms_and_seats(), before)


class AssignSeatsViewTestCase(TestCase):
    def setUp(self):
        self.exam = create_mock_exam()
        PrepStudent.objects.create(exam=self.exam, copy_no=1, sciper=123456, first_name="F", last_name="L", seat="")
        user = create_mock_user()
        user.is_superuser = True
        user.save()
        self.client.force_login(user)
        self.url = reverse("assign_prep_students_seats", kwargs={"exam_pk": self.exam.pk})

    def post(self, **data):
        return self.client.post(self.url, {"first_id": 1, "last_id": 1, "first_number": 1, **data})

    def test_assign(self):
        response = self.post(room="CO 1", seat_pattern="R1-##")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"updated": 1, "first_seat": "R1-01", "last_seat": "R1-01"})

    def test_errors(self):
        self.assertEqual(self.post(first_id="a", room="CO 1").status_code, 400)
        response = self.post(seat_pattern="R1")
        self.assertEqual(response.status_code, 400)
        self.assertIn("no '#'", response.json()["errors"][0])

    def test_finalized_exam_is_locked(self):
        self.exam.is_finalized = True
        self.exam.save()

        self.assertEqual(self.post(room="CO 1").status_code, 403)
        self.assertEqual(PrepStudent.objects.get().room, None)
