import json
from unittest.mock import patch

from examc_app.tests.helpers.prep import PrepViewsTestCase


class LatexFilesViewsTestCase(PrepViewsTestCase):
    def test_edit_gives_the_commands_by_default(self):
        (self.project_path() / "commands.tex").write_text("\\newcommand{\\R}{\\mathbb{R}}\n")

        response = self.client.get(self.url("edit_latex_file"))

        path, contents = json.loads(response.content)
        self.assertEqual((path, contents), ("commands.tex", "\\newcommand{\\R}{\\mathbb{R}}\n"))

    def test_edit_gives_the_packages_file(self):
        (self.project_path() / "packages.tex").write_text("\\usepackage{amsmath}\n")

        path, contents = json.loads(self.client.get(self.url("edit_latex_file"), {"type": "packages"}).content)

        self.assertEqual((path, contents), ("packages.tex", "\\usepackage{amsmath}\n"))

    def test_edit_is_refused_when_the_exam_is_locked(self):
        self.lock()

        self.assertEqual(self.client.get(self.url("edit_latex_file")).status_code, 403)

    def test_save_replaces_the_commands(self):
        commands = self.project_path() / "commands.tex"
        commands.write_text("an old and quite long content that must not remain after the save\n")

        response = self.client.post(self.url("save_latex_edited_file"), {"source": "\\newcommand{\\N}{N}", "type": "commands"})

        self.assertEqual((response.status_code, response.content), (200, b"ok"))
        self.assertEqual(commands.read_text(), "\\newcommand{\\N}{N}")

    def test_save_replaces_the_packages_and_not_the_commands(self):
        project = self.project_path()
        (project / "commands.tex").write_text("commands")

        self.client.post(self.url("save_latex_edited_file"), {"source": "\\usepackage{tikz}", "type": "packages"})

        self.assertEqual((project / "packages.tex").read_text(), "\\usepackage{tikz}")
        self.assertEqual((project / "commands.tex").read_text(), "commands")

    def test_save_is_refused_when_the_exam_is_locked(self):
        commands = self.project_path() / "commands.tex"
        commands.write_text("kept")
        self.lock()

        response = self.client.post(self.url("save_latex_edited_file"), {"source": "lost", "type": "commands"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(commands.read_text(), "kept")


class LatexPackagesViewsTestCase(PrepViewsTestCase):
    AVAILABLE = [{"name": "tikz"}, {"name": "amsmath"}, {"name": "tikz"}]

    def test_edit_lists_the_available_and_the_used_packages(self):
        (self.project_path() / "packages.tex").write_text("\\usepackage{amsmath}\n\\usepackage{xcolor}\n")

        with patch("examc_app.views.preparation.latex.list_available_latex_packages", return_value=self.AVAILABLE):
            body = self.client.get(self.url("edit_latex_packages")).json()

        self.assertEqual(body["latex_available_packages"], ["amsmath", "tikz"])
        self.assertEqual(body["used_packages"], ["amsmath", "xcolor"])

    def test_edit_is_refused_when_the_exam_is_locked(self):
        self.lock()

        self.assertEqual(self.client.get(self.url("edit_latex_packages")).status_code, 403)

    def save(self, packages):
        return self.client.post(self.url("save_latex_edited_packages"), {"new_used_packages[]": packages})

    def test_save_writes_a_usepackage_line_per_package_without_duplicates(self):
        response = self.save(["amsmath", " tikz ", "amsmath", ""])

        self.assertEqual(response.json(), {"success": True, "used_packages": ["amsmath", "tikz"]})
        self.assertEqual((self.project_path() / "packages.tex").read_text(),
                         "% Auto-generated package list\n\\usepackage{amsmath}\n\\usepackage{tikz}\n")

    def test_save_without_packages_empties_the_list(self):
        packages = self.project_path() / "packages.tex"
        packages.write_text("\\usepackage{amsmath}\n")

        response = self.client.post(self.url("save_latex_edited_packages"))

        self.assertEqual(response.json()["used_packages"], [])
        self.assertEqual(packages.read_text(), "% Auto-generated package list\n")

    def test_save_needs_a_post(self):
        response = self.client.get(self.url("save_latex_edited_packages"))

        self.assertEqual(response.status_code, 405)

    def test_save_is_refused_when_the_exam_is_locked(self):
        packages = self.project_path() / "packages.tex"
        packages.write_text("\\usepackage{amsmath}\n")
        self.lock()

        self.assertEqual(self.save(["tikz"]).status_code, 403)
        self.assertEqual(packages.read_text(), "\\usepackage{amsmath}\n")
