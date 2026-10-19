# Changelog
All notable changes to this project will be documented in this file.

The format follows [Semantic Versioning](https://semver.org/).

## [Unreleased]
### Added
- Preparation module: an exam is prepared in the application (first page, sections, single choice, multiple choice,
  true/false and open questions with their answers, Markdown and LaTeX editors, PDF preview), questions can be imported
  from a .tex file, and the print settings (standard or booklet) are set per exam.
- Preparation module: the students of the exam (import from an Excel file, from IS-Academia and the EPFL directory,
  order, seats, export).
- Preparation module: scoring formulas at the exam, section, question and answer levels, with the formula applied and
  its level shown next to each Scoring button.
- Preparation module: the final generation compiles the catalog and the subject, locks the exam while it runs (it can
  be cancelled), and AMC reads the layout and the scoring strategy of the subject itself (layout.sqlite and
  scoring.sqlite of the project), reporting its errors and warnings.

### Fixed
- Preparation module: the views that change the exam only accept POST (a link or an image on another page could delete
  a section or start a generation).
- Preparation module: the preview no longer fails with a Python error instead of its error message when its
  compilation raises.

### Removed
- Unused tables of the preparation module (layout, scan pages, capture boxes, exam copies and score results): the
  layout and the scores are kept by AMC.

## [2.0.2] - 2026-10-12
### Security
- Dependencies: pypdf 6.16.2 -> 6.19.0 and urllib3 2.7.0 -> 2.8.0 (known vulnerabilities reported by the security check).

## [2.0.1] - 2026-10-09
### Fixed
- AMC pages: the dropdown menus open again (the pages loaded a second Bootstrap).
- Review: the copies whose ID of the students list is not their AMC copy number (e.g. anonymous IDs) find their
  pages, corrector boxes and marks (AMC pre-association, \AMCassociation).
- Review: a page holding several questions is graded in the pages group of each question (corrector boxes and
  markers of the group only, markers of the other groups shown read-only, all of them in the marked scan).

## [1.0.0] - 2025-12-10
### Added
- First production version of eXamc - Management of written exams.
- Online review of open questions.
- Generation of statistics and results.
- auto-multiple-choice (AMC) integration.
- User management and secure authentication.
