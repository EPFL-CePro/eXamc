Preview and final generation
============================

Print settings
--------------

**Print settings** sets the **print format**:

- **Standard**: any number of pages per copy.
- **Booklet**: A3 folded and stapled in the middle. The number of pages per copy is a multiple of 4: blank pages are added at the end of each copy when needed, during the final generation.

Preview
-------

**Preview** compiles the exam and shows the PDF in a dialog. It is a **single anonymous copy**, without the list of students, so it is quick: use it to check the texts, the math and the layout while writing. It does not replace the final generation.

If LaTeX fails, the dialog shows its error message.

Final generation
----------------

Click **Generate final**. eXamc first checks the content of the exam and the students.

- The **problems** prevent the generation: they are listed under *Correct these problems before generating*. They include a question without type, a single choice or true/false question without correct answer or with several, a choice question with fewer than 2 answers, an exam without questions, and the problems of the students.
- The **warnings** are probable oversights, listed under *Check these points*, that you can confirm: a question without text, an answer without text, a multiple choice question without correct answer, an open question without answer zone.

Then the generation runs in the background, with a progress bar:

1. the **catalog** is compiled with one anonymous copy: its number of pages gives the number of pages per copy;
2. the **subject** is compiled with one copy per student, all padded to the same number of pages. When some copies are longer (random questions or answers, for example), the subject is compiled again with the longest length, and a warning tells it;
3. the pages of the PDF and of the layout file are compared;
4. **AMC reads the layout** of the subject and **extracts the marks scale** in the project (``layout.sqlite`` and ``scoring.sqlite``): the scans and the marks are processed from them in the AMC module.

The errors and warnings of AMC are shown in the dialog. If a step fails, nothing is finalized.

While it runs, the exam and its students cannot be modified. Use **Cancel generation** in the banner or in the dialog to stop it: it stops within a few seconds and the exam can be edited again.

Final files
-----------

When the generation succeeds, the exam is **finalized**. **Download final files** gives the **Exam subject** and the **Exam catalog** in PDF.

.. warning::

   The final generation rewrites the layout that AMC uses to read the scans. Generate the final files again only before the copies are printed.

Unlock editing
--------------

**Unlock editing** makes the exam editable again after a confirmation. The files already generated may then be inconsistent with the exam: all printed documents should be destroyed, and the final files generated again before use.
