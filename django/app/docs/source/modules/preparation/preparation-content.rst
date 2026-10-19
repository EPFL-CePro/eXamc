Content of the exam
===================

The page of an exam is made of the **first page** and of **sections**, each holding **questions**, each holding **answers**. Every card has its own **Save** button: the changes of a card are written when it is saved, and the LaTeX files of the exam are rewritten.

.. screenshot TODO: Add a screenshot of a section with a single choice question and its answers.

First page
----------

The first page of every copy shows the teachers, the name of the exam, the section of the student, the date and the duration, then the **First page** text written in the first card of the page. The identity of the student is printed from the list of the Students page, one copy per student.

Sections
--------

Use **Add section** to create a section, and the red button of its card to delete it. Each section has:

- a **title** and a **section text**, printed before its questions (it can be only a text, such as grading rules);
- **Randomized questions**: the questions of the section are in a different order on each copy;
- **Start on a new page**: the section starts on a new page.

Drag the handle of a card to change the order of the sections, and the same for the questions of a section and the answers of a question. The positions are renumbered after a deletion.

Questions
---------

Use **Add question** in a section and choose the **title**, the **question type** and, for a choice question, the **number of answers** (at least 2).

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Type
     - Behaviour
   * - **SCQ**
     - Single choice: exactly one correct answer.
   * - **MCQ**
     - Multiple choice: one or more correct answers.
   * - **TF**
     - True or false: two answers, TRUE and FALSE, one of them correct.
   * - **OPEN**
     - Open question, corrected by hand in the **Review** module (see below).

Each question has a **title**, a **question text** and a **Fixed** switch: a question marked **Fixed** starts on a new page.

The answers of a choice question have a **Correct** switch and an **Answer text**.

.. note::

   The switches **Randomized answers** and **Cancel question** of a question, and **Fixed** of an answer, are saved with the exam but are not used yet when the LaTeX files are written: they have no effect on the copies. The order of the answers on a copy is the one decided by AMC.

Open questions
^^^^^^^^^^^^^^

An open question has **Max points** and a **Point increment** (0.5 or 1). The maximum must be a multiple of the increment (for example 2.5 points by steps of 0.5): eXamc refuses other values with a message under the field. The corrector boxes of the question are one box per step, from 0 to the maximum.

Its answers are the **answer zones** printed on the copy: a **grid** or a **blank** zone with a height in millimetres. Use **Add answer** to add a zone.

Texts and editors
-----------------

The texts are written in **Markdown**, with the LaTeX math between ``$...$``. Each editor has two modes:

- **Visual**, a formatted editor with a live preview of the math, using the commands of the **commands** button;
- **Source**, the text as typed.

A text that holds LaTeX commands or an unescaped ``$`` opens in **Source** only, because the visual editor would change it. The **commands** and **packages** buttons of the toolbar edit the LaTeX files shared by all the texts of the exam: macros such as ``\R``, and the ``\usepackage`` lines. Removing every package and saving gives an empty list.

Import questions from a file
----------------------------

**Import questions** in a section adds the questions of a ``.tex`` file at the end of the section. Use **Download the template** in the dialog: it shows one example of each type. A file is made of the environments ``scq``, ``mcq``, ``tf`` and ``open``; the format of the AMC question banks (``\begin{question}``) is also read, and its type comes from the number of correct choices.

Nothing is imported if the file has a problem: the dialog lists every problem with its line number, and the questions already imported are kept.

.. note::

   The import creates the questions with their text, choices and correct answers (and the points, increment and answer zone of an open question). The options of the questions, the scoring formulas and the section settings are not part of the format.
