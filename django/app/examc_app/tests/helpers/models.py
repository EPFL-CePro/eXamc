from django.contrib.auth.models import User

from examc_app.models import Semester, AcademicYear, Exam, Scale


def create_mock_semester(code: int = 20212022, name: str = "Semester test") -> Semester:
    return Semester.objects.create(
        code=code,
        name=name,
    )


def create_mock_academic_year(code: str = "2021", name: str = "Test academic year") -> AcademicYear:
    return AcademicYear.objects.create(
        code=code,
        name=name,
    )


def create_mock_user(
        username: str = "Test User",
        first_name: str = "Test",
        last_name: str = "User",
        email: str = "testuser@test.ch",
        password: str = "testpassword"
) -> User:
    return User.objects.create_user(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        password=password,
    )


def create_mock_exam(
        code: str = "TEST-EXAM",
        name: str = "Test exam",
        semester: Semester | None = None,
        year: AcademicYear | None = None,
) -> Exam:
    if semester is None: semester = create_mock_semester()
    if year is None: year = create_mock_academic_year()

    return Exam.objects.create(
        code=code,
        name=name,
        semester=semester,
        year=year,
    )


def create_mock_scale(
    name="Test scale",
    total_points=100,
    points_to_add=0,
    min_grade=1,
    max_grade=6,
    rounding=1,
    formula="",
    exam=None,
    final=False,
) -> Scale:
    return Scale.objects.create(
        name=name,
        total_points=total_points,
        points_to_add=points_to_add,
        min_grade=min_grade,
        max_grade=max_grade,
        rounding=rounding,
        formula=formula,
        exam=exam,
        final=final,
    )