.. eXamc documentation master file, created by
   sphinx-quickstart on Wed Mar 13 16:10:47 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to eXamc's documentation!
=================================

**eXamc** is a web application developed by an EPFL team. This application allows several users to prepare, review and correct exams on the same platform.
It also supports workflows based on Auto Multiple Choice (AMC).

.. warning::

   This project is under active development. In case of technical issues please contact cepro-exam@epfl.ch

.. container:: twocol

    .. container:: leftside

        **Procedure for teacher**

      - Connect to your ENTRA ID account
      - Use the Dashboard to open an exam or continue pending work
      - Upload the AMC project
      - Check that AMC working documents and layout detection are ready
      - Enable the required modules in Exam Info
      - Add teachers, reviewers or assistants in Exam Info
      - In Review settings, configure pages groups
      - Assign reviewers to pages groups
      - Configure grading schemes when needed
      - Upload scans in Review
      - Correct open questions
      - Correct the MCQ using AMC
      - Generate statistics and results
      - Export your data

    .. container:: rightside

        **Procedure for reviewer**

      - Connect to your ENTRA ID account
      - Use the Dashboard to find pending review work
      - Open the assigned Review pages group
      - Correct the open questions



Contents
--------
.. toctree::
   :maxdepth: 4

   modules/dashboard/dashboard
   modules/open_exam/open_exam
   modules/create_exam/create_exam
   modules/room_plan/room_plan
   modules/exam_info/exam_info
   modules/review/review
   modules/amc/amc
   modules/results/results
   modules/statistic/statistics
   modules/import_data/import_data
   modules/export_data/export_data



Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
