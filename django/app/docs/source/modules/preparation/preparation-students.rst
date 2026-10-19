Students
========

The **Students** page lists the students of the exam. The final generation prints **one copy per student**, with the identity, the room and the seat of the student on the first page. The page has two steps, **1. Get the students** and **2. Arrange them**, and a table of the students below.

.. screenshot TODO: Add a screenshot of the Students page with the two steps and the table.

1. Get the students
-------------------

Two ways to fill the list. Both **replace all the students of the exam** (a confirmation is asked when there are some):

- **Import from IS-Academia**: the students enrolled in the course of the exam. The IDs follow the alphabetical order of their last names; the rooms and seats are given in step 2.
- **From an Excel file**: **Download the empty template**, fill it with one student per row, then **Import the file**. **SCIPER** and **SEAT** are required, **ROOM** is optional. The IDs follow the order of the rows. A row without seat is imported and shown in yellow, to be completed in the table.

The names, emails and sections come from the EPFL directory. A SCIPER that is not found there is imported **to be corrected**: change it in the table. A file with a problem imports nothing, and the dialog lists every problem with its row.

2. Arrange them
---------------

**In eXamc**

1. **Order**: **Renumber the IDs** by last and first name, by SCIPER, by section then name, by room and seat, or at random. The IDs are the **copy numbers**; the rooms and seats stay with each student. For seats in a random order, renumber randomly first, then assign the seats.
2. **Rooms & seats**: give a **Room** and numbered seats to the students with an ID from a first to a last ID. In the seats, one run of ``#`` is the seat number with leading zeros: ``R1-##`` gives R1-01, R1-02… Leave the room or the seats empty to keep the current ones, and repeat for each room. A preview tells which students get which seats before it is sent.

**One student**: the pencil button of the table changes its ID (the others shift), room, seat and the other fields.

**In Excel**: **Download the current list**, reorder the rows (the IDs follow the order of the rows), fill in the rooms and seats, then **Import the file**.

Before the final generation
---------------------------

The final generation refuses to start when:

- the exam has no students;
- some students must still be corrected (SCIPER not found);
- some students have no seat;
- the IDs are not 1, 2, 3… without gaps (renumber them);
- a field of a student (name, email, room, seat…) holds a comma or a double quote.

The students and the exam cannot be modified while a final generation runs or once the exam is finalized.
