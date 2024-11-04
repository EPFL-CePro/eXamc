.. eXamc documentation master file, created by
   sphinx-quickstart on Wed Mar 13 16:10:47 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to eXamc's documentation!
=================================

**eXamc** is a web application developed by an EPFL team. This application allows several users to correct exams on the same platform.
It also allows the use of auto-multiple-choice software.

.. warning::

   This project is under active development. In case of technical issues please contact cepro-exam@epfl.ch

.. container:: twocol

    .. container:: leftside

        **Procedure for teacher**

      - Connect to your Tequila account
      - Open a exam
      - Upload your AMC project
      - Upload your scans in Review
      - Assign new reviewer in Exam Infos
      - In review settings, create your questions
      - Correct open questions
      - Correct the MCQ using AMC
      - Generate your results
      - Export your data

    .. container:: rightside

        **Procedure for reviewer**

      - Connect to your Tequila account
      - Have a coffee
      - Correct the open questions



Contents
--------
.. toctree::
   :maxdepth: 4

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


