import re
from dataclasses import dataclass, field

from examc_app.models import ExamBuild, ExamBuildQuestion


AMC_MESSAGE_PATTERNS = {
    "student": re.compile(r"\\message\{ETU=([0-9]+)\}"),
    "alias": re.compile(r"\\message\{BR=([0-9]+)\}"),
    "question": re.compile(r"\\message\{Q=([0-9]+)\}"),
    "question_partial": re.compile(r"\\message\{QPART\}"),
    "question_end": re.compile(r"\\message\{FQ\}"),
    "question_title": re.compile(r"\\message\{NUM=([0-9]+)=(.+)\}"),
    "multiple": re.compile(r"\\message\{MULT\}"),
    "indicative": re.compile(r"\\message\{INDIC\}"),
    "answer": re.compile(r"\\message\{REP=([0-9]+):([BM])\}"),
    "strategy": re.compile(r"\\message\{B=(.+)\}"),
    "default_simple": re.compile(r"\\message\{BDS=(.+)\}"),
    "default_multiple": re.compile(r"\\message\{BDM=(.+)\}"),
    "variable": re.compile(r"\\message\{VAR:([0-9a-zA-Z.:-]+)=(.+)\}"),
    "total": re.compile(r"\\message\{TOTAL=([\s0-9]+)\}"),
}


class ScoringExtractionError(Exception):
    pass


@dataclass
class ParsedAnswer:
    answer_number: int
    is_correct: bool
    strategy: str = ""


@dataclass
class ParsedQuestion:
    amc_question_number: int
    title: str = ""
    is_multiple: bool = False
    is_indicative: bool = False
    is_partial: bool = False
    answers: dict = field(default_factory=dict)
    question_strategy: str = ""


@dataclass
class ParsedStudentSheet:
    student_number: int
    alias_of: int | None = None
    questions: dict = field(default_factory=dict)
    main_strategy: str = ""


@dataclass
class ParsedAmcScoring:
    total_sheets: int | None = None
    default_simple_strategy: str = ""
    default_multiple_strategy: str = ""
    variables: dict = field(default_factory=dict)
    question_titles: dict = field(default_factory=dict)  # amc internal number -> rendered_id
    students: list = field(default_factory=list)


def load_amc_log_lines(amc_log_path):
    with open(amc_log_path, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()


def parse_amc_scoring_log(amc_log_path) -> ParsedAmcScoring:
    """
    Parse AMC .amc log file into a structured Python object.

    This follows the same core message patterns used by AMC-prepare.pl.
    """
    lines = load_amc_log_lines(amc_log_path)
    parsed = ParsedAmcScoring()

    current_student = None
    current_question = None

    for raw_line in lines:
        line = raw_line.strip()

        m = AMC_MESSAGE_PATTERNS["total"].search(line)
        if m:
            total_raw = m.group(1).replace(" ", "")
            parsed.total_sheets = int(total_raw) if total_raw.isdigit() else None
            continue

        m = AMC_MESSAGE_PATTERNS["student"].search(line)
        if m:
            student_number = int(m.group(1))
            current_student = ParsedStudentSheet(student_number=student_number)
            parsed.students.append(current_student)
            current_question = None
            continue

        m = AMC_MESSAGE_PATTERNS["alias"].search(line)
        if m and current_student:
            current_student.alias_of = int(m.group(1))
            continue

        m = AMC_MESSAGE_PATTERNS["question_title"].search(line)
        if m:
            amc_question_number = int(m.group(1))
            rendered_id = m.group(2)
            parsed.question_titles[amc_question_number] = rendered_id
            continue

        m = AMC_MESSAGE_PATTERNS["question"].search(line)
        if m and current_student:
            amc_question_number = int(m.group(1))

            current_question = current_student.questions.get(amc_question_number)
            if current_question is None:
                current_question = ParsedQuestion(amc_question_number=amc_question_number)
                current_student.questions[amc_question_number] = current_question

            if amc_question_number in parsed.question_titles:
                current_question.title = parsed.question_titles[amc_question_number]

            continue

        m = AMC_MESSAGE_PATTERNS["question_partial"].search(line)
        if m and current_question:
            current_question.is_partial = True
            continue

        m = AMC_MESSAGE_PATTERNS["question_end"].search(line)
        if m:
            current_question = None
            continue

        m = AMC_MESSAGE_PATTERNS["multiple"].search(line)
        if m and current_question:
            current_question.is_multiple = True
            continue

        m = AMC_MESSAGE_PATTERNS["indicative"].search(line)
        if m and current_question:
            current_question.is_indicative = True
            continue

        m = AMC_MESSAGE_PATTERNS["answer"].search(line)
        if m and current_question:
            answer_number = int(m.group(1))
            answer_state = m.group(2)  # B = correct, M = wrong

            current_question.answers[answer_number] = ParsedAnswer(
                answer_number=answer_number,
                is_correct=(answer_state == "B"),
            )
            continue

        m = AMC_MESSAGE_PATTERNS["strategy"].search(line)
        if m:
            strategy = m.group(1)

            if current_student and current_question:
                # question-level strategy unless a more detailed answer strategy system
                # is added later
                if current_question.question_strategy:
                    current_question.question_strategy += "," + strategy
                else:
                    current_question.question_strategy = strategy
            elif current_student:
                if current_student.main_strategy:
                    current_student.main_strategy += "," + strategy
                else:
                    current_student.main_strategy = strategy
            continue

        m = AMC_MESSAGE_PATTERNS["default_simple"].search(line)
        if m:
            parsed.default_simple_strategy = m.group(1)
            continue

        m = AMC_MESSAGE_PATTERNS["default_multiple"].search(line)
        if m:
            parsed.default_multiple_strategy = m.group(1)
            continue

        m = AMC_MESSAGE_PATTERNS["variable"].search(line)
        if m:
            var_name = m.group(1)
            var_value = m.group(2)
            if var_name == "postcorrect":
                var_name = "postcorrect_flag"
            parsed.variables[var_name] = var_value
            continue

    return parsed


def validate_parsed_amc_scoring(parsed: ParsedAmcScoring):
    """
    Basic sanity checks inspired by AMC's own validation logic.
    Returns a list of warning/error strings.
    """
    issues = []

    for student in parsed.students:
        for amc_question_number, question in student.questions.items():
            if question.title and not question.is_multiple and not question.is_partial:
                n_correct = sum(1 for answer in question.answers.values() if answer.is_correct)
                n_total = len(question.answers)

                if n_total > 0 and n_correct != 1 and not question.is_indicative:
                    issues.append(
                        f"Question '{question.title}' for student {student.student_number} "
                        f"has {n_correct}/{n_total} correct answers but is not multiple-choice."
                    )

    return issues


def map_parsed_scoring_to_build(build: ExamBuild, parsed: ParsedAmcScoring):
    """
    Map parsed AMC question titles / rendered IDs onto ExamBuildQuestion rows.

    Returns a structure ready for persistence or further grading logic.
    """
    build_questions_by_rendered_id = {
        question.rendered_id: question
        for question in ExamBuildQuestion.objects.filter(build=build).prefetch_related("build_answers")
    }

    mapped_students = []

    for student in parsed.students:
        mapped_questions = []

        for amc_question_number, parsed_question in student.questions.items():
            rendered_id = parsed_question.title or parsed.question_titles.get(amc_question_number, "")
            build_question = build_questions_by_rendered_id.get(rendered_id)

            mapped_answers = []
            if build_question:
                build_answers_by_number = {
                    answer.rendered_answer_number: answer
                    for answer in build_question.build_answers.all()
                }

                for answer_number, parsed_answer in parsed_question.answers.items():
                    mapped_answers.append(
                        {
                            "answer_number": answer_number,
                            "build_answer": build_answers_by_number.get(answer_number),
                            "is_correct": parsed_answer.is_correct,
                            "strategy": parsed_answer.strategy,
                        }
                    )

            mapped_questions.append(
                {
                    "amc_question_number": amc_question_number,
                    "rendered_id": rendered_id,
                    "build_question": build_question,
                    "is_multiple": parsed_question.is_multiple,
                    "is_indicative": parsed_question.is_indicative,
                    "is_partial": parsed_question.is_partial,
                    "question_strategy": parsed_question.question_strategy,
                    "answers": mapped_answers,
                }
            )

        mapped_students.append(
            {
                "student_number": student.student_number,
                "alias_of": student.alias_of,
                "main_strategy": student.main_strategy,
                "questions": mapped_questions,
            }
        )

    return {
        "total_sheets": parsed.total_sheets,
        "default_simple_strategy": parsed.default_simple_strategy,
        "default_multiple_strategy": parsed.default_multiple_strategy,
        "variables": parsed.variables,
        "students": mapped_students,
    }


def extract_scoring_from_amc_log(build: ExamBuild, amc_log_path=None, validate=True):
    """
    High-level entrypoint:
    - parse build.amc_log_path
    - validate it
    - map to build snapshot objects

    Returns a dict ready to be consumed by your grading layer.
    """
    amc_log_path = amc_log_path or build.amc_log_path
    if not amc_log_path:
        raise ScoringExtractionError("No amc_log_path provided and build.amc_log_path is empty")

    parsed = parse_amc_scoring_log(amc_log_path)
    issues = validate_parsed_amc_scoring(parsed) if validate else []
    mapped = map_parsed_scoring_to_build(build, parsed)

    return {
        "parsed": parsed,
        "issues": issues,
        "mapped": mapped,
    }