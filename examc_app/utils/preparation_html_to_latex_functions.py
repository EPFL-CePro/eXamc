from pathlib import Path
import re
import pypandoc
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET

from examc import settings
from examc_app.models import PrepSection, PrepQuestion, PrepQuestionAnswer, BOX_TYPE_CHOICES, Exam
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

# def mathml_to_latex_simple(mathml: str) -> str:
#     root = ET.fromstring(mathml)
#
#     def strip_ns(tag):
#         return tag.split("}", 1)[-1]
#
#     def walk(node):
#         tag = strip_ns(node.tag)
#
#         if tag in ["math", "mrow"]:
#             return "".join(walk(c) for c in node)
#
#         if tag == "semantics":
#             for c in node:
#                 if strip_ns(c.tag) != "annotation":
#                     return walk(c)
#             return ""
#
#         if tag == "mi":
#             text = (node.text or "").strip()
#             if node.attrib.get("mathvariant") == "double-struck":
#                 return rf"\mathbb{{{text}}}"
#             return text
#
#         if tag == "mn":
#             return (node.text or "").strip()
#
#         if tag == "mo":
#             text = (node.text or "").strip()
#             return {
#                 "∈": r"\in",
#                 "∖": r"\setminus",
#                 "⊂": r"\subset",
#                 "≤": r"\le",
#                 "≥": r"\ge",
#                 "≠": r"\neq",
#                 ":": ":",
#             }.get(text, text)
#
#         if tag == "mfrac":
#             children = list(node)
#             if len(children) == 2:
#                 return rf"\frac{{{walk(children[0])}}}{{{walk(children[1])}}}"
#             return ""
#
#         if tag == "msup":
#             children = list(node)
#             if len(children) == 2:
#                 return rf"{walk(children[0])}^{{{walk(children[1])}}}"
#             return ""
#
#         return "".join(walk(c) for c in node)
#
#     return walk(root)

# def preprocess_math_html(html_text: str) -> str:
#     soup = BeautifulSoup(html_text, "html.parser")
#
#     for math_node in soup.select(".note-math"):
#         latex_node = math_node.select_one(".note-latex")
#
#         if latex_node and latex_node.text.strip():
#             latex = latex_node.text.strip()
#             math_node.replace_with(soup.new_string(f"${latex}$"))
#             continue
#
#         mathml_node = math_node.select_one(".katex-mathml math")
#         if mathml_node is not None:
#             latex = mathml_to_latex_simple(str(mathml_node))
#             math_node.replace_with(soup.new_string(f"${latex}$"))
#             continue
#
#         katex_node = math_node.select_one(".katex")
#         if katex_node is not None:
#             # rendered math exists, but no reliable source latex
#             # remove the rendered widget but keep surrounding plain text if any
#             katex_node.decompose()
#
#         math_node.unwrap()
#
#     return str(soup)

# def preprocess_images(soup):
#     for img in soup.find_all("img"):
#         src = img.get("src", "").strip()
#
#         if not src:
#             img.decompose()
#             continue
#
#         # remove style attributes
#         img.attrs = {"src": src}
#
#     return soup

# def preprocess_summernote_html(html_text: str) -> str:
#     soup = BeautifulSoup(html_text or "", "html.parser")
#
#     # 1. Convert math blocks to raw LaTeX
#     for math_node in soup.select(".note-math"):
#         latex = None
#
#         latex_node = math_node.select_one(".note-latex")
#         if latex_node and latex_node.text.strip():
#             latex = latex_node.text.strip()
#
#         if not latex:
#             mathml_node = math_node.select_one(".katex-mathml math")
#             if mathml_node is not None:
#                 try:
#                     latex = mathml_to_latex_simple(str(mathml_node))
#                 except Exception:
#                     latex = None
#
#         if latex:
#             math_node.replace_with(soup.new_string(f"${latex}$"))
#             continue
#
#         # No reliable LaTeX source: remove rendered KaTeX but keep text around it
#         for katex in math_node.select(".katex"):
#             katex.decompose()
#
#         math_node.unwrap()
#
#     # 2. Clean images
#     for img in soup.find_all("img"):
#         src = (img.get("src") or "").strip()
#
#         if not src:
#             img.decompose()
#             continue
#
#         # Keep only safe/needed attrs
#         attrs = {"src": src}
#
#         alt = (img.get("alt") or "").strip()
#         if alt:
#             attrs["alt"] = alt
#
#         img.attrs = attrs
#
#     # 3. Remove inline styles/classes from normal tags
#     for tag in soup.find_all(True):
#         if tag.name == "img":
#             continue
#         if tag.name == "a":
#             href = tag.get("href")
#             tag.attrs = {"href": href} if href else {}
#         else:
#             tag.attrs = {}
#
#     return str(soup)

# def normalize_summernote_html(html: str) -> str:
#     html = html or ""
#     html = re.sub(r"<p>\s*(<br\s*/?>)?\s*</p>", "", html, flags=re.I)
#     return html.strip()


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

# def html_to_latex_pandoc(html: str) -> str:
#     html = preprocess_summernote_html(html)
#     html = normalize_summernote_html(html)
#     html = replace_unicode_math_and_text(html)
#
#     latex = pypandoc.convert_text(
#         html,
#         to="latex",
#         format="html",
#         extra_args=[
#             "--wrap=none",
#         ],
#     )
#
#     latex = postprocess_latex(latex)
#     return latex

def update_exam_latex(exam: Exam):
    amc_project_path = get_amc_project_path(exam, False)
    amc_project_template_path = str(settings.AMC_PROJECTS_ROOT) + "/templates/base"
    template_exam_latex_path = amc_project_template_path + "/exam_template.tex"
    exam_latex_path_output = amc_project_path + "/exam.tex"
    exam_template = Path(template_exam_latex_path).read_text(encoding="utf-8")
    exam_tex = exam_template

    #first update first page
    template_first_page_latex_path = amc_project_template_path + "/first_page_template.tex"
    first_page_latex_path_output = amc_project_path + "/first_page.tex"
    render_first_page_tex_from_html(exam, exam.first_page_text, template_first_page_latex_path, first_page_latex_path_output)

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

        exam_tex = (
            exam_tex
            .replace(PH_SECTIONS, f"\input{{./{section_filename}}} \n" + f"{PH_SECTIONS}")
            .replace(PH_SECTIONS_INSERT, f"\input{{./{section_header_filename}}} \n" + f"{PH_SECTIONS_INSERT}")
            .replace(PH_SECTIONS_INSERT, f"\insertgroup{{{section_grp_name}}} \n" + f"{PH_SECTIONS_INSERT}")
        )

    Path(exam_latex_path_output).write_text(exam_tex, encoding="utf-8")
    return exam_latex_path_output

def render_first_page_tex_from_html(exam: Exam, html: str, template_path: str, output_path: str) -> str:
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
        final_tex = final_tex.replace(VAR_NB_PAGES, "\\getpagerefnumber{LastPage}")

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
        .replace(PH_QUESTION_ID, f'{question.question_type.code}-{question.position}')
    )

    if question.new_page:
        question_tex = question_tex.replace(PH_NEW_PAGE,r'\newpage')

    if question.question_type.code == 'OPEN':
        question_tex = (
            question_tex
            .replace(PH_QUESTION_TITLE, f'{question.title}')
            .replace(PH_CORR_POINTS, corr_box_number_to_text(float(question.max_points), float(question.point_increment)))
            .replace(PH_QUESTION_ID, f'{question.question_type.code}-{question.position}')
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

    if answer.prep_question.question_type.code == 'OPEN':
        if answer.box_type == BOX_TYPE_CHOICES[0]:
            answer_type_text = f'\\SplitOpenGrid{{{answer.box_height_mm}mm}}'
        else:
            answer_type_text = f'\\SplitOpenBox{{{answer.box_height_mm}mm}}'

    else:
        if answer.is_correct:
            answer_type_text = f'\correctchoice{{{latex_fragment_text}}}'
        else:
            answer_type_text = f'\wrongchoice{{{latex_fragment_text}}}'

    question_tex = question_tex.replace(
        PH_QUESTION_ANSWERS,
        answer_type_text + "\n" + f"{PH_QUESTION_ANSWERS}")

    return question_tex

