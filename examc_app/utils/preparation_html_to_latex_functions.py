from pathlib import Path
import re
import pypandoc


def normalize_summernote_html(html: str) -> str:
    # minimal cleanup; you can improve this later
    html = html or ""

    # remove some useless empty paragraphs Summernote often creates
    html = re.sub(r"<p>\s*(<br\s*/?>)?\s*</p>", "", html, flags=re.I)

    return html.strip()


def postprocess_latex(latex: str) -> str:
    """
    Small cleanup after pandoc.
    Adapt this to your template/style.
    """
    latex = latex.strip()

    # collapse excessive blank lines
    latex = re.sub(r"\n{3,}", "\n\n", latex)

    # Example: if you do not want top-level section commands produced somewhere
    # latex = latex.replace(r"\section{", r"\textbf{")

    return latex


def html_to_latex_pandoc(html: str) -> str:
    html = normalize_summernote_html(html)

    latex = pypandoc.convert_text(
        html,
        to="latex",
        format="html",
        extra_args=[
            "--wrap=none",
        ],
    )

    latex = postprocess_latex(latex)
    return latex


def render_first_page_tex_from_html(
        html: str,
        template_path: str,
        output_path: str,
        placeholder: str = "%FIRST-PAGE-TEXT%",
) -> str:
    template = Path(template_path).read_text(encoding="utf-8")
    latex_fragment = html_to_latex_pandoc(html)

    if placeholder not in template:
        raise ValueError(f"Placeholder {placeholder!r} not found in template")

    final_tex = template.replace(placeholder, latex_fragment)
    Path(output_path).write_text(final_tex, encoding="utf-8")
    return final_tex
