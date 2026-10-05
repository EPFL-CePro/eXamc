from django.test import SimpleTestCase

from examc_app.utils.preparation_latex_functions import extract_katex_macros


class ExtractKatexMacrosTestCase(SimpleTestCase):
    def test_newcommand_and_def(self):
        macros = extract_katex_macros(
            "\\newcommand{\\R}{\\mathbb{R}}%\n"
            "\\newcommand\\xx{{ x}}\n"
            "\\newcommand{\\fracpd}[2]{{\\frac{\\partial #1}{\\partial #2}}}% TEXTSTYLE\n"
            "\\def\\guille#1{\\guillemotleft\\,#1\\,\\guillemotright}%\n"
            "\\def\\Spc{\\ }%\n"
        )

        self.assertEqual(macros["\\R"], "\\mathbb{R}")
        self.assertEqual(macros["\\xx"], "{ x}")
        self.assertEqual(macros["\\fracpd"], "{\\frac{\\partial #1}{\\partial #2}}")
        self.assertEqual(macros["\\guille"], "\\guillemotleft\\,#1\\,\\guillemotright")
        self.assertEqual(macros["\\Spc"], "\\ ")

    def test_comments_are_ignored(self):
        macros = extract_katex_macros(
            "%\\newcommand{\\hidden}{x}\n"
            "\\def\\funcdef#1#2%{DOMAIN}{IMAGE}\n"
            "    {#1 \\to #2}%\n"
        )

        self.assertNotIn("\\hidden", macros)
        self.assertEqual(macros["\\funcdef"], "#1 \\to #2")

    def test_later_definition_wins(self):
        macros = extract_katex_macros(
            "\\newcommand{\\Varphi}{{\\varphi}}\n"
            "\\renewcommand{\\Varphi}{{\\theta}}\n"
            "\\providecommand{\\Varphi}{{\\psi}}\n"
        )

        self.assertEqual(macros["\\Varphi"], "{\\theta}")

    def test_let_copies_the_current_definition(self):
        macros = extract_katex_macros(
            "\\newcommand{\\first}{a}\n"
            "\\let\\copy=\\first\n"
            "\\renewcommand{\\first}{b}\n"
            "\\let\\phi=\\varphi%\n"
            "\\let\\LeftBrace=(% DEFAULT [\n"
        )

        self.assertEqual(macros["\\copy"], "a")
        self.assertEqual(macros["\\first"], "b")
        self.assertEqual(macros["\\phi"], "\\varphi")
        self.assertEqual(macros["\\LeftBrace"], "(")

    def test_recursive_macros_are_dropped(self):
        macros = extract_katex_macros(
            "\\let\\oldint=\\int\n"
            "\\def\\int{\\oldint\\limits}\n"
            "\\def\\dd{{ \\,d}}\n"
        )

        self.assertNotIn("\\int", macros)
        self.assertNotIn("\\oldint", macros)
        self.assertEqual(macros["\\dd"], "{ \\,d}")

    def test_unsupported_definitions_are_ignored(self):
        macros = extract_katex_macros(
            "\\def\\delimited#1.{#1}\n"
            "\\newcommand{\\withdefault}[2][x]{#1#2}\n"
            "\\newenvironment{Matrix}[1]{\\left(}{\\right)}\n"
        )

        self.assertEqual(macros, {})

    def test_tex_spacing_assignments_are_removed(self):
        macros = extract_katex_macros(
            "\\def\\ffrac#1#2{\\mathinner{\\raisebox{0.5pt}{\\footnotesize{\\mathsurround0pt$\\dfrac{#1}{#2}$}}}}\n"
        )

        self.assertEqual(macros["\\ffrac"], "\\mathinner{\\raisebox{0.5pt}{\\footnotesize{$\\dfrac{#1}{#2}$}}}")
