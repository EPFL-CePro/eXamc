from dataclasses import dataclass, field

from django.db.models import Prefetch

from examc_app.models import Exam, PrepQuestion, PrepQuestionAnswer, PrepSection

# Question types (QuestionType.code) whose answers are boxes to tick
CHOICE_TYPES = ("SCQ", "MCQ", "TF")
# Exactly one correct answer: AMC refuses a simple question with several, and none makes it impossible to succeed
SINGLE_ANSWER_TYPES = ("SCQ", "TF")


@dataclass
class ExamChecks:
    """
    Problems of the exam content before the final generation, for the user. `errors` prevent the generation (the
    correction would be wrong, or the compilation would fail); `warnings` are probably oversights but may be wanted,
    the user confirms them.
    """
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _has_text(text) -> bool:
    return bool((text or "").strip())


def _section_label(section: PrepSection) -> str:
    return f'Section "{section.title}"'


def _question_label(question: PrepQuestion, number: int) -> str:
    code = question.question_type.code if question.question_type else "no type"
    return f'{_section_label(question.prep_section)}, question {number} "{question.title}" ({code})'


def _check_choice_question(question: PrepQuestion, label: str, answers: list[PrepQuestionAnswer],
                           checks: ExamChecks) -> None:
    code = question.question_type.code
    correct = sum(answer.is_correct for answer in answers)

    if code == "TF":
        if len(answers) != 2:
            checks.errors.append(f"{label}: a true/false question needs its 2 answers TRUE and FALSE.")
            return
    elif len(answers) < 2:
        checks.errors.append(f"{label}: at least 2 answers are needed.")
        return

    if code in SINGLE_ANSWER_TYPES:
        if correct == 0:
            checks.errors.append(f"{label}: no correct answer.")
        elif correct > 1:
            checks.errors.append(f"{label}: {correct} correct answers, only one is allowed.")
    elif correct == 0:
        checks.warnings.append(f"{label}: no correct answer (the students must tick none).")

    if code != "TF":
        empty = [str(number) for number, answer in enumerate(answers, start=1) if not _has_text(answer.answer_text)]
        if empty:
            checks.warnings.append(f"{label}: answer {', '.join(empty)} without text.")


def _check_open_question(label: str, answers: list[PrepQuestionAnswer], checks: ExamChecks) -> None:
    # The answers with a box type are the answer zones (see render_answer_tex_from_html), the others the points
    if not any(answer.box_type and answer.box_height_mm for answer in answers):
        checks.warnings.append(f"{label}: no answer zone (no space to write on the copy).")


def check_exam_content(exam: Exam) -> ExamChecks:
    """The problems of the sections, questions and answers of the exam (see ExamChecks)."""
    checks = ExamChecks()
    sections = (
        exam.prepSections.order_by("position")
        .prefetch_related(Prefetch(
            "prepQuestions",
            queryset=PrepQuestion.objects.select_related("question_type").order_by("position").prefetch_related(
                Prefetch("prepAnswers", queryset=PrepQuestionAnswer.objects.order_by("position"))
            ),
        ))
    )

    questions_count = 0
    for section in sections:
        questions = list(section.prepQuestions.all())
        if not questions:
            checks.warnings.append(f"{_section_label(section)}: no question.")
            continue

        for number, question in enumerate(questions, start=1):
            questions_count += 1
            label = _question_label(question, number)
            if question.question_type is None:
                checks.errors.append(f"{label}: no question type.")
                continue
            if not _has_text(question.question_text):
                checks.warnings.append(f"{label}: no question text.")

            answers = list(question.prepAnswers.all())
            if question.question_type.code in CHOICE_TYPES:
                _check_choice_question(question, label, answers, checks)
            elif question.question_type.code == "OPEN":
                _check_open_question(label, answers, checks)

    if not questions_count:
        checks.errors.insert(0, "The exam has no questions.")
    return checks
