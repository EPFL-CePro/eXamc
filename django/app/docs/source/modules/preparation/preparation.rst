Preparation
===========

The **Preparation** module prepares an exam inside eXamc, without writing the LaTeX of an AMC project by hand. The first page, the sections, the questions and their answers are entered in the application, and eXamc writes the LaTeX files of the AMC project.

At the end, the **final generation** produces the subject and the catalog to print, and lets AMC read the layout of the copies and the marks scale. The scans and the marks are then processed in the **AMC** module.

The module is available to the users who can manage the exam, when **Preparation** is enabled in **Exam Info**. Open it with the **Prepare** button of the Dashboard or with the **Preparation** menu of the sidebar.

.. screenshot TODO: Add a screenshot of the Preparation page showing the toolbar, the first page and a section.

Workflow
--------

1. Create the exam with **Create exam** and enable **Preparation** in **Exam Info**.
2. Write the **first page**, add the **sections** and their **questions** (see :doc:`preparation-content`).
3. Optionally define the **scoring formulas** (see :doc:`preparation-scoring`).
4. Import the **students** and give them their rooms and seats (see :doc:`preparation-students`).
5. Choose the **print format** and check the result with **Preview**.
6. Click **Generate final**, then download the files (see :doc:`preparation-final-generation`).
7. Continue in the **AMC** module: upload the scans and correct.

The toolbar
-----------

The toolbar of the Preparation page gives access to:

- **Default questions scorings**: the scoring formulas of the whole exam;
- **commands** and **packages**: the LaTeX commands and packages used by the texts of the exam;
- **Students**: the page of the students of the exam;
- **Print settings**: standard or booklet printing;
- **Preview**: a PDF of the exam, with a single anonymous copy;
- **Generate final**, which becomes **Download final files** once the exam is finalized.

Locked exam
-----------

The exam, and its students, cannot be modified in two cases:

- a **final generation is running**: a banner tells who started it and when, and it can be cancelled from the banner;
- the exam is **finalized**: the final generation has succeeded. To modify the exam again, use **Unlock editing**.

All the buttons that modify the exam are then disabled, and the server refuses the changes.

.. toctree::
   :maxdepth: 1

   preparation-content
   preparation-scoring
   preparation-students
   preparation-final-generation
