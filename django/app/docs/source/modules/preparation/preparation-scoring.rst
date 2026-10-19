Scoring formulas
================

A scoring formula tells AMC how many points a correct and a wrong answer give. It is written as AMC does, for example ``b=1,m=0`` (1 point for a correct answer, 0 for a wrong one) or ``b=1,m=-1``. The **Scoring** dialog has a help panel with the available values and examples.

.. screenshot TODO: Add a screenshot of the Scoring dialog and of the scoring text next to a question.

The four levels
---------------

Formulas can be given at four levels, each with its own **Scoring** button:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Level
     - Where
   * - **Global**
     - The **Default questions scorings** button of the toolbar: one formula per question type (SCQ, MCQ, TF) for the whole exam.
   * - **Section**
     - The **Scoring** button of a section: one formula per question type for the questions of this section.
   * - **Question**
     - The **Scoring** button of a question: one formula for this question.
   * - **Answer**
     - The **Scoring** button of an answer: one formula for this answer.

At the global and section levels, a formula is given to a **question type**, and each type can be used once per level. The characters ``%``, ``\``, ``{``, ``}`` and ``#`` are refused in a formula, because it is written as is in the LaTeX.

Which formula is applied
------------------------

A question gets the formula of the most specific level that has one: its own formula, then the formula of its section for its question type, then the formula of the whole exam for its question type. When no level has a formula, **AMC applies its own default**. An answer has its own formula if it has one, otherwise the one of its question.

The open questions are scored by their corrector boxes: they have no **Scoring** button.

What the page shows
-------------------

Next to the **Scoring** button of each question and answer, a short text tells which formula is applied and from which level, for example:

- ``Global : "b=3,m=-1"``
- ``Section : "b=2,m=0"``
- ``Question : "b=5"``
- ``Answer : "b=9"``
- ``AMC default`` when no level has a formula.

A small black frame in the **Scoring** button of a level lists what it defines: the question types that have a formula (for example ``MCQ, SCQ``) at the global and section levels, and ``Custom`` for a question or an answer that has its own formula. A level without formula keeps the button as it is.

The texts and the frames are updated when the **Scoring** dialog is closed, since a formula of the exam or of a section changes what the other questions apply.
