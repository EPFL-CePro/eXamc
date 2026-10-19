import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction

from examc_app.models import PrepQuestion, PrepSection, QuestionType
from examc_app.utils.preparation_functions import (
    create_prep_answer, create_prep_question, renumber_answers, update_open_answers)

TEMPLATE_PATH = Path(__file__).with_name("questions_import_template.tex")

MAX_FILE_SIZE = 1024 * 1024
# \\begin{Question} (the format of the AMC question bank) gets its type from the number of correct choices
QUESTION_ENVIRONMENTS = ("scq", "mcq", "tf", "open", "question")
CHOICES_ENVIRONMENTS = ("choices", "choiceshoriz")
OPEN_BOX_TYPES = ("grid", "blank")
OPEN_DEFAULTS = {"points": "1", "increment": "1", "box": "grid", "height": "50"}

QUESTION_START_RE = re.compile(
    r"\\begin\{(" + "|".join(QUESTION_ENVIRONMENTS) + r")\}[ \t]*\{([^}\n]*)\}[ \t]*(?:\[([^\]\n]*)\])?[ \t]*",
    re.IGNORECASE,
)
CHOICES_START_RE = re.compile(r"\\begin\{(" + "|".join(CHOICES_ENVIRONMENTS) + r")\}(?:[ \t]*\[[^\]\n]*\])?(?:[ \t]*\{[^}\n]*\})?")
CHOICE_RE = re.compile(r"\\(correctchoice|wrongchoice)\s*(?=\{)")
ANSWER_RE = re.compile(r"\\answer\s*\{\s*(true|false)\s*\}", re.IGNORECASE)


class QuestionsImportError(Exception):
    """The file cannot be imported: nothing is created, `errors` are shown to the user."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass
class ParsedChoice:
    text: str
    is_correct: bool


@dataclass
class ParsedQuestion:
    type_code: str
    title: str
    text: str
    line: int
    choices: list[ParsedChoice] = field(default_factory=list)
    tf_correct: bool | None = None
    open_options: dict[str, str] = field(default_factory=dict)


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _strip_comment_lines(text: str) -> str:
    """Blanks the lines starting with % (keeps the line numbers)."""
    return "\n".join("" if line.lstrip().startswith("%") else line for line in text.split("\n"))


def _braced(text: str, start: int) -> tuple[str, int] | None:
    """The content of the {...} group opening at `start` (escaped braces and nested groups included), with the
    index after its closing brace."""
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
        index += 1
    return None


def _clean(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().split("\n")).strip()


def _parse_choices(body: str, line: int, label: str, errors: list[str]) -> tuple[str, list[ParsedChoice]]:
    """Splits the body of a choice question into its text and its choices."""
    start = CHOICES_START_RE.search(body)
    if not start:
        errors.append(f"{label}: no \\begin{{choices}} block.")
        return body, []
    end = re.search(r"\\end\{(" + "|".join(CHOICES_ENVIRONMENTS) + r")\}", body[start.end():])
    if not end:
        errors.append(f"{label}: \\begin{{choices}} is never closed.")
        return body[:start.start()], []

    content = body[start.end():start.end() + end.start()]
    choices = []
    position = 0
    while True:
        match = CHOICE_RE.search(content, position)
        if not match:
            break
        group = _braced(content, match.end())
        if not group:
            errors.append(f"{label}: unbalanced braces in a choice.")
            break
        text, position = group
        choices.append(ParsedChoice(_clean(text), match.group(1) == "correctchoice"))
    return body[:start.start()], choices


def _parse_open_options(raw: str | None, label: str, errors: list[str]) -> dict[str, str]:
    options = dict(OPEN_DEFAULTS)
    for item in filter(None, (part.strip() for part in (raw or "").split(","))):
        key, separator, value = item.partition("=")
        key, value = key.strip().lower(), value.strip()
        if not separator or key not in OPEN_DEFAULTS:
            errors.append(f"{label}: unknown option \"{item}\" (points, increment, box, height).")
            continue
        options[key] = value

    try:
        points, increment = Decimal(options["points"]), Decimal(options["increment"])
        if points < 0 or increment not in (Decimal("0.5"), Decimal("1")):
            errors.append(f"{label}: points must be 0 or more and increment 0.5 or 1.")
        elif points % increment != 0:
            errors.append(f"{label}: points must be a multiple of the increment.")
    except InvalidOperation:
        errors.append(f"{label}: points and increment must be numbers.")
    if options["box"] not in OPEN_BOX_TYPES:
        errors.append(f"{label}: box must be grid or blank.")
    if not options["height"].isdigit() or int(options["height"]) <= 0:
        errors.append(f"{label}: height must be a whole number of mm.")
    return options


def parse_questions_tex(content: str) -> list[ParsedQuestion]:
    """The questions of an import file (see questions_import_template.tex). Raises QuestionsImportError with every
    problem found."""
    text = _strip_comment_lines(content.replace("\r\n", "\n").replace("\r", "\n"))
    errors: list[str] = []
    questions: list[ParsedQuestion] = []
    position = 0

    while True:
        start = QUESTION_START_RE.search(text, position)
        if not start:
            break
        environment = start.group(1)
        kind = environment.lower()
        title = start.group(2).strip()
        line = _line_of(text, start.start())
        label = f'Line {line}, {kind} "{title}"'

        end = re.search(r"\\end\{" + re.escape(environment) + r"\}", text[start.end():], re.IGNORECASE)
        if not end:
            errors.append(f"{label}: \\end{{{environment}}} not found.")
            break
        body = text[start.end():start.end() + end.start()]
        position = start.end() + end.end()

        # A % ending the \\begin line is a LaTeX comment hiding the line break
        body = re.sub(r"^%[^\n]*", "", body)
        if not title:
            errors.append(f"{label}: the title is empty.")

        question = ParsedQuestion(type_code=kind.upper(), title=title, text="", line=line)
        if kind in ("scq", "mcq", "question"):
            question.text, question.choices = _parse_choices(body, line, label, errors)
            correct = sum(choice.is_correct for choice in question.choices)
            if len(question.choices) < 2:
                errors.append(f"{label}: at least two choices are needed.")
            if kind == "question":
                question.type_code = "SCQ" if correct <= 1 else "MCQ"
            if question.type_code == "SCQ" and correct != 1:
                errors.append(f"{label}: a single choice question needs exactly one \\correctchoice (found {correct}).")
            for number, choice in enumerate(question.choices, start=1):
                if not choice.text:
                    errors.append(f"{label}: choice {number} is empty.")
        elif kind == "tf":
            answers = ANSWER_RE.findall(body)
            if len(answers) != 1:
                errors.append(f"{label}: a true/false question needs one \\answer{{true}} or \\answer{{false}}.")
            else:
                question.tf_correct = answers[0].lower() == "true"
            question.text = ANSWER_RE.sub("", body)
        else:
            question.open_options = _parse_open_options(start.group(3), label, errors)
            question.text = body
        if start.group(3) and kind != "open":
            errors.append(f"{label}: options between brackets are only for open questions.")

        question.text = _clean(question.text)
        questions.append(question)

    if not questions and not errors:
        errors.append("No question found: use the scq, mcq, tf and open environments of the template.")
    if errors:
        raise QuestionsImportError(errors)
    return questions


def decode_questions_file(data: bytes) -> str:
    if len(data) > MAX_FILE_SIZE:
        raise QuestionsImportError(["The file is too big (1 MB max)."])
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise QuestionsImportError(["The file is not a text file."])


@transaction.atomic
def import_questions(section: PrepSection, questions: list[ParsedQuestion]) -> list[PrepQuestion]:
    """Adds the questions at the end of the section."""
    types = {question_type.code: question_type for question_type in QuestionType.objects.all()}
    missing = sorted({question.type_code for question in questions} - set(types))
    if missing:
        raise QuestionsImportError([f"Unknown question type: {', '.join(missing)}."])

    created = []
    for parsed in questions:
        question = create_prep_question(section, types[parsed.type_code], title=parsed.title[:500])
        question.question_text = parsed.text

        if parsed.type_code in ("SCQ", "MCQ"):
            for number, choice in enumerate(parsed.choices, start=1):
                create_prep_answer(question, title=f"Answer {number}", answer_text=choice.text,
                                   is_correct=choice.is_correct)
        elif parsed.type_code == "TF":
            for answer in question.prepAnswers.all():
                answer.is_correct = (answer.title == "TRUE") == parsed.tf_correct
                answer.save(update_fields=["is_correct"])
        else:
            options = parsed.open_options
            question.max_points = Decimal(options["points"])
            question.point_increment = options["increment"]
            box = create_prep_answer(question, title="Answer zone")
            box.box_type = options["box"]
            box.box_height_mm = int(options["height"])
            box.save(update_fields=["box_type", "box_height_mm"])
            update_open_answers(question)

        question.save()
        renumber_answers(question)
        created.append(question)
    return created
