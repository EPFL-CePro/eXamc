Seating map
=============

The **Seating map** tool generates room plans for exams. It can preview or download a seating map based on the selected rooms and numbering options.

This web app is under development. Contact lucile.pinard@epfl.ch in case of issue.

.. screenshot TODO: Add or refresh a Default seating map screenshot showing room selection, options, Preview Seat Map and Download Seat Map.

Options:
----------
Numbering option:
^^^^^^^^^^^^^^^^^
The default page supports continuous numbering and special numbering. Continuous numbering fills the room normally. Special numbering uses a CSV file containing one number per line, for example ``A12``, ``24`` or ``E``.

Skipping option:
^^^^^^^^^^^^^^^^
The skip option skips numbers listed in a CSV file. The program skips those numbers without leaving empty seats in the room plan.

To use the "skipping option", please check the "fill all seat" button and put the number one in the "first seat number".

Fill all seats:
^^^^^^^^^^^^^^^
The **Fill all seats** option fills every seat in the selected rooms. It starts from the first seat number.

Special file:
^^^^^^^^^^^^^
The special file field is displayed when special numbering or skipping is selected. Upload a CSV file with one value per line.

To use "special file" option, please check the "fill all seat" button and put the number one in the "first seat number".

Shape to draw:
^^^^^^^^^^^^^^^
Two shapes can be used to draw seat labels: circle and square.

Procedure:
------------
* Select rooms.
* Select the required options.
* Upload a CSV file if the special file field appears.
* Enable **Fill all seats** when needed.
* Enter the first seat number.
* Click **Preview Seat Map** to check the result.
* Click **Download Seat Map** to download the file.

.. note::

   Info bubbles are available directly on the page

For the interactive special plan, use:

.. toctree::
   :maxdepth: 1

   room_plan_special
