import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
import re
import pypandoc

from examc import settings
from examc_app.models import PrepSection, PrepQuestion, PrepQuestionAnswer, BOX_TYPE_CHOICES, Exam, ScoringStrategy
from examc_app.utils.amc_functions import get_amc_project_path

#PLACEHOLDERS FOR TEMPLATES
PH_NEW_PAGE = '%NEW-PAGE%'
PH_SECTIONS = '%SECTIONS%'
PH_SECTIONS_INSERT = '%SECTIONS-INSERT%'
PH_FIRST_PAGE_TXT = '%FIRST-PAGE-TEXT%'
PH_TEACHER = '%TEACHER%'
PH_EXAM_NAME = '%EXAM-NAME%'
PH_EXAM_DATE = '%EXAM-DATE%'
PH_EXAM_TIME = '%EXAM-TIME%'
PH_SECTION_TITLE = '%SECTION-TITLE%'
PH_SECTION_TEXT = '%SECTION-TEXT%'
PH_SECTION_ID = '%SECTION-ID%'
PH_SECTION_RANDOM = '%SECTION-RANDOM%'
PH_SECTION_QUESTIONS = '%QUESTIONS%'
PH_QUESTION_ID = '%QUESTION-ID%'
PH_QUESTION_TEXT = '%QUESTION-TEXT%'
PH_QUESTION_TYPE = '%QUESTION-TYPE%'
PH_QUESTION_ANSWERS = '%ANSWERS%'
PH_ANSWER_TYPE = '%ANSWER-TYPE%'
PH_ANSWER_TEXT = '%ANSWERS-TEXT%'
PH_CORR_POINTS = '%CORR-POINTS%'
PH_QUESTION_TITLE = '%QUESTION-TITLE%'

#USABLE VARIABLES
VAR_NB_PAGES = r"\{NB-PAGES\}"

def corr_box_number_to_text(n: float, inc: float) -> str:
    units = {
        0: "Zero", 1: "One", 2: "Two", 3: "Three", 4: "Four",
        5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine",
        10: "Ten", 11: "Eleven", 12: "Twelve", 13: "Thirteen",
        14: "Fourteen", 15: "Fifteen", 16: "Sixteen",
        17: "Seventeen", 18: "Eighteen", 19: "Nineteen",
        20: "Twenty"
    }

    integer_part = int(n)
    decimal_part = n - integer_part

    if inc == 1:
        return units[integer_part]
    else:
        if decimal_part == 0.5:
            return units[integer_part] + "HalfHalf"
        elif decimal_part == 0:
            return units[integer_part] + "Half"
        else:
            raise ValueError("Only .5 increments are supported")

def replace_unicode_math_and_text(html: str) -> str:
    replacements = {
        "\u00a0": " ",          # nbsp
        "∈": r"\in ",
        "∉": r"\notin ",
        "⊂": r"\subset ",
        "⊆": r"\subseteq ",
        "⊃": r"\supset ",
        "⊇": r"\supseteq ",
        "∖": r"\setminus ",
        "≤": r"\le ",
        "≥": r"\ge ",
        "≠": r"\neq ",
        "≈": r"\approx ",
        "∞": r"\infty ",
        "→": r"\to ",
        "←": r"\leftarrow ",
        "×": r"\times ",
        "±": r"\pm ",
        "∪": r"\cup ",
        "∩": r"\cap ",
        "∅": r"\emptyset ",
        "ℕ": r"\mathbb{N}",
        "ℝ": r"\mathbb{R}",
        "ℤ": r"\mathbb{Z}",
        "ℚ": r"\mathbb{Q}",
        "ℂ": r"\mathbb{C}",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "--",
        "—": "---",
        "…": r"\ldots{}",
    }

    for src, dst in replacements.items():
        html = html.replace(src, dst)

    return html


def postprocess_latex(latex: str) -> str:
    latex = latex.strip()
    latex = re.sub(r"\n{3,}", "\n\n", latex)

    # Optional: scale images automatically
    latex = re.sub(
        r"\\includegraphics\{([^}]+)\}",
        r"\\includegraphics[width=0.8\\linewidth]{\1}",
        latex,
    )

    return latex

def markdown_to_latex_pandoc(markdown: str) -> str:
    latex = pypandoc.convert_text(
        markdown or "",
        to="latex",
        format="markdown+tex_math_dollars",
        extra_args=["--wrap=none"],
    )
    return postprocess_latex(latex)

def write_exam_generated_vars(project_path: str, pages_per_copy: int | None) -> str:
    if pages_per_copy is None:
        pages_value = "2"
    else:
        pages_value = str(int(pages_per_copy))

    vars_tex_path = Path(project_path) / "examc_generated_vars.tex"
    vars_tex_path.write_text(
        "% Auto-generated file - do not edit\n"
        f"\\newcommand{{\\TotalPagesPerCopy}}{{{pages_value}}}\n",
        encoding="utf-8",
    )
    return str(vars_tex_path)

def update_exam_latex(exam: Exam, pages_per_copy: int | None = None):
    amc_project_path = get_amc_project_path(exam, False)
    amc_project_template_path = str(settings.AMC_PROJECTS_ROOT) + "/templates/base"
    template_exam_latex_path = amc_project_template_path + "/exam_template.tex"
    exam_latex_path_output = amc_project_path + "/exam.tex"
    exam_template = Path(template_exam_latex_path).read_text(encoding="utf-8")
    exam_tex = exam_template
    write_exam_generated_vars(amc_project_path, pages_per_copy)

    #first update first page
    template_first_page_latex_path = amc_project_template_path + "/first_page_template.tex"
    first_page_latex_path_output = amc_project_path + "/first_page.tex"
    render_first_page_tex_from_html(exam, exam.first_page_text, template_first_page_latex_path, first_page_latex_path_output,pages_per_copy)

    for section in exam.prepSections.order_by("position").all():
        template_section_header_latex_path = amc_project_template_path + "/section_header_template.tex"
        section_header_filename = f"section_header_{section.position}.tex"
        section_grp_name = f"SECTION-{section.position}"
        section_header_latex_path_output = amc_project_path + "/" + section_header_filename
        render_section_header_tex_from_html(section, template_section_header_latex_path, section_header_latex_path_output)

        template_section_latex_path = amc_project_template_path + "/section_template.tex"
        section_filename = f"section_{section.position}.tex"
        section_latex_path_output = amc_project_path + "/" + section_filename
        section_latex_file_path = render_section_tex_from_html(section, template_section_latex_path,
                                                               section_latex_path_output)

        for question in section.prepQuestions.order_by("position").all():
            if question.question_type.code != 'OPEN':
                template_question_latex_path = amc_project_template_path + "/scq_mcq_tf_template.tex"
            else:
                template_question_latex_path = amc_project_template_path + "/open_template.tex"

            render_question_tex_from_html(question, section_latex_file_path, template_question_latex_path)

            if question.question_type.code != 'OPEN':
                update_question_scoring_latex_file(question.pk)

        exam_tex = (
            exam_tex
            .replace(PH_SECTIONS, f"\\input{{./{section_filename}}} \n" + f"{PH_SECTIONS}")
            .replace(PH_SECTIONS_INSERT, f"\\input{{./{section_header_filename}}} \n" + f"{PH_SECTIONS_INSERT}")
            .replace(PH_SECTIONS_INSERT, f"\\insertgroup{{{section_grp_name}}} \n" + f"{PH_SECTIONS_INSERT}")
        )

    Path(exam_latex_path_output).write_text(exam_tex, encoding="utf-8")
    return exam_latex_path_output

def render_first_page_tex_from_html(exam: Exam, html: str, template_path: str, output_path: str, pages_per_copy: int = None) -> str:
    template = Path(template_path).read_text(encoding="utf-8")
    latex_fragment = markdown_to_latex_pandoc(html)

    if PH_FIRST_PAGE_TXT not in template:
        raise ValueError(f"Placeholder {PH_FIRST_PAGE_TXT!r} not found in template")
    if PH_TEACHER not in template:
        raise ValueError(f"Placeholder {PH_TEACHER!r} not found in template")
    if PH_EXAM_NAME not in template:
        raise ValueError(f"Placeholder {PH_EXAM_NAME!r} not found in template")
    if PH_EXAM_DATE not in template:
        raise ValueError(f"Placeholder {PH_EXAM_DATE!r} not found in template")
    if PH_EXAM_TIME not in template:
        raise ValueError(f"Placeholder {PH_EXAM_TIME!r} not found in template")

    teacher_txt = ''
    for exam_user in exam.exam_users.filter(group_id=2):
        if teacher_txt:
            teacher_txt += ', '
        teacher_txt += f'{exam_user.user.first_name[0]}. {exam_user.user.last_name}'

    exam_name_txt = f'({exam.code}) {exam.name}'
    exam_date = exam.date.strftime("%d.%m.%Y")
    exam_time = exam.duration if exam.duration else ''


    final_tex = (
        template
        .replace(PH_FIRST_PAGE_TXT, latex_fragment)
        .replace(PH_TEACHER, teacher_txt)
        .replace(PH_EXAM_NAME, exam_name_txt)
        .replace(PH_EXAM_DATE, exam_date)
        .replace(PH_EXAM_TIME, exam_time)
    )

    if VAR_NB_PAGES in final_tex:
        if pages_per_copy is not None:
            final_tex = final_tex.replace(VAR_NB_PAGES, str(pages_per_copy))
        else:
            # fallback for preview / early compile
            final_tex = final_tex.replace(VAR_NB_PAGES, "??")

    Path(output_path).write_text(final_tex, encoding="utf-8")
    return output_path

def render_section_header_tex_from_html(section: PrepSection, template_path: str, output_path: str) -> str:
    template = Path(template_path).read_text(encoding="utf-8")
    latex_fragment_title = markdown_to_latex_pandoc(section.title)
    latex_fragment_text = markdown_to_latex_pandoc(section.section_text)

    if PH_SECTION_TITLE not in template:
        raise ValueError(f"Placeholder {PH_SECTION_TITLE!r} not found in template")
    elif PH_SECTION_TEXT not in template:
        raise ValueError(f"Placeholder {PH_SECTION_TEXT!r} not found in template")

    final_tex = (
        template
        .replace(PH_SECTION_TITLE, latex_fragment_title)
        .replace(PH_SECTION_TEXT, latex_fragment_text)
    )

    Path(output_path).write_text(final_tex, encoding="utf-8")
    return output_path

def render_section_tex_from_html(section: PrepSection, template_path: str, output_path: str) -> str:
    template = Path(template_path).read_text(encoding="utf-8")

    if PH_SECTION_ID not in template:
        raise ValueError(f"Placeholder {PH_SECTION_ID!r} not found in template")
    elif PH_SECTION_RANDOM not in template:
        raise ValueError(f"Placeholder {PH_SECTION_RANDOM!r} not found in template")

    random_text = 'withoutreplacement' if section.random_questions else 'fixed'

    final_tex = (
        template
        .replace(PH_SECTION_ID, f"SECTION-{section.position}")
        .replace(PH_SECTION_RANDOM, random_text)
    )

    Path(output_path).write_text(final_tex, encoding="utf-8")
    return output_path


def render_question_tex_from_html(question: PrepQuestion, section_path: str, template_path: str) -> str:
    template = Path(template_path).read_text(encoding="utf-8")
    section = Path(section_path).read_text(encoding="utf-8")
    latex_fragment_text = markdown_to_latex_pandoc(question.question_text)

    if PH_QUESTION_TEXT not in template:
        raise ValueError(f"Placeholder {PH_QUESTION_TEXT!r} not found in template")
    elif PH_SECTION_ID not in template:
        raise ValueError(f"Placeholder {PH_SECTION_ID!r} not found in template")
    elif not question.question_type.code == 'OPEN' and PH_QUESTION_TYPE not in template:
        raise ValueError(f"Placeholder {PH_QUESTION_TYPE!r} not found in template")
    elif PH_QUESTION_ID not in template:
        raise ValueError(f"Placeholder {PH_QUESTION_ID!r} not found in template")
    elif not question.question_type.code == 'OPEN' and PH_ANSWER_TYPE not in template:
        raise ValueError(f"Placeholder {PH_ANSWER_TYPE!r} not found in template")
    elif question.question_type.code == 'OPEN' and PH_CORR_POINTS not in template:
        raise ValueError(f"Placeholder {PH_CORR_POINTS!r} not found in template")
    elif question.question_type.code == 'OPEN' and PH_QUESTION_TITLE not in template:
        raise ValueError(f"Placeholder {PH_QUESTION_TITLE!r} not found in template")

    if question.question_type.code == 'MCQ':
        question_type_text = 'questionmult'
        answer_type_text = 'choices'
    elif question.question_type.code == 'OPEN':
        question_type_text = None
        answer_type_text = None
    elif question.question_type.code == 'SCQ':
        question_type_text = 'question'
        answer_type_text = 'choices'
    else:
        question_type_text = 'question'
        answer_type_text = 'choiceshoriz'

    question_tex = (
        template
        .replace(PH_QUESTION_TEXT, latex_fragment_text)
        .replace(PH_SECTION_ID, f'SECTION-{question.prep_section.position}')
        .replace(PH_QUESTION_ID, f'SECTION-{question.prep_section.position}-{question.question_type.code}-{question.position}')
    )

    if question.new_page:
        question_tex = question_tex.replace(PH_NEW_PAGE,r'\newpage')

    if question.question_type.code == 'OPEN':
        question_tex = (
            question_tex
            .replace(PH_QUESTION_TITLE, f'{question.title}')
            .replace(PH_CORR_POINTS, corr_box_number_to_text(float(question.max_points), float(question.point_increment)))
            .replace(PH_QUESTION_ID, f'SECTION-{question.prep_section.position}-{question.question_type.code}-{question.position}')
        )
    else:
        question_tex = (
            question_tex
            .replace(PH_ANSWER_TYPE, f'{answer_type_text}')
            .replace(PH_QUESTION_TYPE, question_type_text)
        )

    if question.question_type.code == 'TF':
        question_tex = question_tex.replace(f'ANSWER-{answer_type_text}',f'ANSWER-{answer_type_text}[0]')

    for answer in question.prepAnswers.all():
        question_tex = render_answer_tex_from_html(answer, question_tex)
        if question.question_type.code != 'OPEN':
            update_answer_scoring_latex_file(answer.pk)

    section_tex = section.replace(
        PH_SECTION_QUESTIONS,
        f"{question_tex} \n" + f"{PH_SECTION_QUESTIONS}"
    )

    Path(section_path).write_text(section_tex, encoding="utf-8")
    return section_path

def render_answer_tex_from_html(answer: PrepQuestionAnswer, question_tex: str) -> str:
    if answer.prep_question.question_type.code == 'TF':
        latex_fragment_text = 'TRUE' if answer.is_correct else 'FALSE'
    elif answer.prep_question.question_type.code == 'OPEN':
        latex_fragment_text = answer.title
    else:
        latex_fragment_text = markdown_to_latex_pandoc(answer.answer_text)

    if PH_QUESTION_ANSWERS not in question_tex:
        raise ValueError(f"Placeholder {PH_QUESTION_ANSWERS!r} not found in template")

    answer_type_text = None
    if answer.prep_question.question_type.code == 'OPEN':
        if answer.box_type:
            if answer.box_type == BOX_TYPE_CHOICES[0]:
                answer_type_text = f'\\SplitOpenGrid{{{answer.box_height_mm}mm}}'
            else:
                answer_type_text = f'\\SplitOpenBox{{{answer.box_height_mm}mm}}'
    else:
        if answer.is_correct:
            answer_type_text = f'\\correctchoice{{{latex_fragment_text}}}'
        else:
            answer_type_text = f'\\wrongchoice{{{latex_fragment_text}}}'

    if answer_type_text:
        question_tex = question_tex.replace(
            PH_QUESTION_ANSWERS,
            answer_type_text + "\n" + f"{PH_QUESTION_ANSWERS}")

    return question_tex

## scoring formulas
def update_global_scoring_latex_file(scoring_formulas,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    amc_project_path = Path(get_amc_project_path(exam, False))
    filepath = amc_project_path / "global_scoring.tex"

    lines = []

    for scoring_formula in scoring_formulas:
        if scoring_formula.question_type.code == 'SCQ':
            lines.append(f"\\baremeDefautS{{{scoring_formula.formula}}}")
        elif scoring_formula.question_type.code == 'MCQ':
            lines.append(f"\\baremeDefautM{{{scoring_formula.formula}}}")
        elif scoring_formula.question_type.code == 'TF':
            lines.append(f"\\newcommand{{\\baremeDefautTF}}{{{scoring_formula.formula}}}")

    content = "% Auto-generated scoring formulas\n"
    if lines:
        content += "\n".join(lines) + "\n"

    filepath.write_text(content, encoding="utf-8")

    return True

def update_question_scoring_latex_file(question_pk):
    question = PrepQuestion.objects.get(pk=question_pk)
    if question.prepQuestionScoringFormulas.exists() :
        scoring_formula = question.prepQuestionScoringFormulas.first()
        amc_project_path = Path(get_amc_project_path(question.prep_section.exam, False))
        section_filename = f"section_{question.prep_section.position}.tex"
        file_path = amc_project_path / section_filename
        question_latex_id = f"SECTION-{question.prep_section.position}-{question.question_type.code}-{question.position}"

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        pattern = re.compile(
            rf".*\\begin{{(question(?:mult)?)}}{{{re.escape(question_latex_id)}}}(?:\\bareme{{.*?}})?\s*$"
        )

        new_lines = []
        for line in lines:
            m = pattern.search(line)
            if m:
                env = m.group(1)
                new_lines.append(f"\\begin{{{env}}}{{{question_latex_id}}}\\bareme{{{scoring_formula.formula}}}\n")
            else:
                new_lines.append(line)

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    return True

def update_answer_scoring_latex_file(answer_pk):
    answer = PrepQuestionAnswer.objects.get(pk=answer_pk)
    if answer.prepAnswersScoringFormulas.exists() :
        scoring_formula = answer.prepAnswersScoringFormulas.first()
        amc_project_path = Path(get_amc_project_path(answer.prep_question.prep_section.exam, False))
        section_filename = f"section_{answer.prep_question.prep_section.position}.tex"
        file_path = amc_project_path / section_filename
        answer_txt = markdown_to_latex_pandoc(answer.answer_text)
        question_latex_id = f"SECTION-{answer.prep_question.prep_section.position}-{answer.prep_question.question_type.code}-{answer.prep_question.position}"

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Match one full question block for the given code
        block_pattern = re.compile(
            rf"""
            \\begin{{question(?:mult)?}}{{{re.escape(question_latex_id)}}}   # question start
            (?:\\bareme{{.*?}})?                                # optional bareme
            .*?                                                 # block content
            \\end{{question}}                                   # question end
            """,
            re.DOTALL | re.VERBOSE,
        )

        def update_block(match):
            block = match.group(0)

            # Match a choice line containing exactly the wanted answer text
            answer_pattern = re.compile(
                rf"^(.*?(?:\\correctchoice|\\wrongchoice){{{re.escape(answer_txt)}}})(\s*)$",
                re.MULTILINE,
            )

            def repl_answer(m):
                return f"{m.group(1)}\\bareme{{{scoring_formula.formula}}}{m.group(2)}"

            new_block, n = answer_pattern.subn(repl_answer, block, count=1)
            return new_block

        new_content, n_blocks = block_pattern.subn(update_block, content, count=1)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return True

# functions to get LaTeX package installed on server
INTERNAL_PATTERNS = [
    r"-\d{4}-\d{2}-\d{2}$",   # rollback/versioned files like xparse-2020-10-01
    r"^latexrelease$",
    r"^fixltx2e$",
    r"^expl3.*$",
    r"^l3.*$",
]

_internal_res = [re.compile(p) for p in INTERNAL_PATTERNS]


def has_kpsewhich() -> bool:
    return shutil.which("kpsewhich") is not None


def run_cmd(args):
    return subprocess.run(args, capture_output=True, text=True)


@lru_cache(maxsize=1)
def get_tex_search_paths() -> list[str]:
    if not has_kpsewhich():
        return []

    result = run_cmd(["kpsewhich", "-show-path=tex"])
    if result.returncode != 0:
        return []

    sep = ";" if os.name == "nt" else ":"
    raw_paths = result.stdout.strip().split(sep)

    paths = []
    for p in raw_paths:
        p = p.strip()
        if not p:
            continue

        p = os.path.expanduser(p)

        # Skip kpathsea path modifiers / non-real entries
        if p.startswith("!!"):
            p = p[2:]

        # Ignore unresolved brace-ish or recursive markers if present
        if p in {"", ".", "//"}:
            continue

        # Keep existing dirs only
        if os.path.isdir(p):
            paths.append(os.path.normpath(p))

    # Deduplicate while preserving order
    return list(dict.fromkeys(paths))


def is_user_selectable_package(name: str) -> bool:
    if not name:
        return False
    return not any(rx.match(name) or rx.search(name) for rx in _internal_res)


@lru_cache(maxsize=1)
def list_available_latex_packages() -> list[str]:
    packages = []

    for base in get_tex_search_paths():
        for root, _, files in os.walk(base):
            for filename in files:
                if not filename.endswith(".sty"):
                    continue

                name = filename[:-4]
                if is_user_selectable_package(name):
                    packages.append({"name":name,"selected":None})

    return packages

def extract_used_packages(file_contents: str) -> list[str]:
    used = []

    matches = re.findall(
        r"\\usepackage(?:\[[^\]]*\])?\{([^}]*)\}",
        file_contents
    )

    for match in matches:
        for pkg in match.split(","):
            pkg = pkg.strip()
            if pkg:
                used.append(pkg)

    return used


def package_exists(package_name: str) -> bool:
    if not has_kpsewhich():
        return False

    result = run_cmd(["kpsewhich", f"{package_name}.sty"])
    return result.returncode == 0 and bool(result.stdout.strip())