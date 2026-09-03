##############################
Grading schemes
##############################

Grading schemes define predefined marking items that reviewers can check during correction. They are useful when a question can be marked with a structured list of expected elements, partial-credit items or adjustments.

Enable grading schemes
----------------------

To use grading schemes for a pages group:

- open **Review -> Settings**;
- go to **Pages groups**;
- enable **Use Grading Scheme** for the relevant group;
- click **Save**;
- open the **Grading Schemes** tab.

.. screenshot TODO: Refresh so the current Pages groups tab and Use Grading Scheme switch are visible.

.. image:: images/review_settings_grading-schemes.png
  :width: 800


Manage schemes
--------------

The **Grading Schemes** tab shows one tab for each pages group where grading schemes are enabled. Inside a pages group, use the green **+** button to add a grading scheme.

For each scheme, define:

- **Name**, used by reviewers to select the scheme;
- **Max points**, the maximum number of points for the scheme;
- **Description**, used to explain when and how the scheme should be applied.

Click **Save** after editing a scheme.

Delete is disabled once a grading scheme is used in Review.

Checkboxes
----------

Checkboxes are the individual marking items inside a grading scheme. Each checkbox has a name, a point value and a description.

To add a checkbox, click the green **+** button in the checkbox section. The sum of checkbox points is displayed next to the maximum points, and it is highlighted when the total does not match the scheme maximum.

Use the drag handle to reorder checkboxes. Click **Save** after changing names, points, descriptions or order.

When a grading scheme has already been used in Review, checkbox points, add and delete actions are locked. Existing descriptions and other allowed fields can still be reviewed according to the fields available in the form.

.. screenshot TODO: Refresh so page-group tabs, scheme tabs, drag handles, points total and lock states are visible.


.. image:: images/grading_schemes.png
  :width: 800


During correction
-----------------

During correction, the reviewer selects the grading scheme and checks the items matching the student's answer.

The **ZERO** item represents zero points. The **ADJ** item is used for point adjustments when the answer is incomplete but deserves partial credit.

.. screenshot TODO: Refresh so the current Review-side grading scheme panel and checkbox behavior are visible.


.. image:: images/correction_grading_schemes.png
  :width: 400
