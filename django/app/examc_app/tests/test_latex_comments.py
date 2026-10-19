from django.test import SimpleTestCase

from examc_app.utils.preparation_latex_functions import markdown_to_latex_pandoc


class LatexCommentsTestCase(SimpleTestCase):
    def test_comment_lines_stay_comments(self):
        latex = markdown_to_latex_pandoc(
            "%*****%\n"
            "% \\noindent\\ScalNotation{a $x$}\n"
            "\\ifx\\ScalNotation\\undefined{b}\\else\\fi\n"
            "\n"
            "Text\n"
            "\n"
            "% second comment\n"
        )

        lines = latex.splitlines()
        self.assertIn("%*****%", lines)
        self.assertIn("% \\noindent\\ScalNotation{a $x$}", lines)
        self.assertIn("% second comment", lines)
        self.assertNotIn("\\%", latex)
        # The line after the comment is not part of it
        self.assertIn("\\ifx\\ScalNotation\\undefined{b}\\else\\fi", lines)

    def test_percent_in_a_code_block_is_escaped_not_a_comment(self):
        latex = markdown_to_latex_pandoc("```python\n% not a comment\nx = 50 % 3\n```\n")

        self.assertNotIn("\n% not a comment", "\n" + latex)
        self.assertIn("50", latex)
        self.assertIn("\\%", latex)

    def test_percent_inside_a_line_is_still_escaped(self):
        self.assertIn("50\\%", markdown_to_latex_pandoc("Score 50% of the points"))
