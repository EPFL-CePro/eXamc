# Changelog
All notable changes to this project will be documented in this file.

The format follows [Semantic Versioning](https://semver.org/).

## [Unreleased]
- 

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
