AMC application
===============

First, you have to check if in the Project tab everything's ok. Check if the to infos bar are green.

.. image:: images/project.png
   :width: 600

If it doesn't, click Update Documents and Layout Detection.

Import the scans
----------------

.. image:: images/AMCData_capture.png
   :width: 600


#. Go to the "Data capture" tab
#. Click on the "Automatic" button
#. Upload or choose to import from app your scans

.. image:: images/automatic_data_capture.png
   :width: 400


Check the boxes with the "sensitivity" setting
----------------------------------------------------


This step allows you to check the boxes (a trace in a box, a cross incorrectly erased, etc.).

#. Click on the "Manual" button.
#. Click on the "Sensibility" column twice to sort the copies to check.
#. Check all those with a value greater than 0. The software counts as checked all those with a red square. To deselect a box, click on it.

.. image:: images/AMC_correct_manual.png
   :width: 600

Check the boxes with the "invalid" parameter
---------------------------------------------

Invalids are where students have selected multiple boxes for questions with only one correct answer (SCQ, True-false).


#. Click on the "Marking" tab.
#. Check the "Update marking scale" box.
#. Click on the "Mark" button.
#. Go back to the "Data capture" tab
#. Click on the "Manual" button.
#. Select the parameters: inv
#. Select / deselect the desired boxes and move to the next ones using the ">" button.

Check open questions for which no points have been awarded
-----------------------------------------------------------

'empty' is used to check whether all the boxes in a question are empty. You can use it to check that an open question has been forgotten.

From "Data capture" tab

#. Click on the "Manual" button.
#. Select the settings: empty.
#. Select the first ID of your open question to be checked.
#. Make sure you start checking by being on copy 1 page 1 and click the ">" button to move to the next copy where points are missing.
#. Correct the question and select the box to award the correct number of points.
#. Click the ">" button until the software finds nothing more.
#. Repeat this step for the other open questions


Calculate the results
----------------------

#. Go back to the "Marking" tab.
#. Check the "Update marking scale" box.
#. Click on the "Mark" button.

.. image:: images/AMCMarking.png
   :width: 600

Associate the students list
~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. If you modified the name of student list CSV file, you can select the other CSV list by clicking on "set file" button
#. Select the primary key you want to sort by
#. Click on the "Automatic" button.

Export the results
-------------------

#. Click on the "report" tab
#. Click on generate results
#. To export the annotated pdfs:

* Select "One file per student".
* Click on "Annotate" button.


.. image:: images/AMCResults.png
   :width: 600