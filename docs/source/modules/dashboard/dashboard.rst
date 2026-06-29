Dashboard
=========

The Dashboard is the first page displayed after login. It gives each user a role-based overview of the exams they can access and the next actions they can take.

.. screenshot TODO: Add a new Dashboard overview screenshot showing My exams, filters/search, To do and Shortcuts.

My exams
--------

The **My exams** table lists the most recent exams available to the current user. For each exam, the dashboard shows:

- the exam code and name;
- the exam date;
- the user's role on the exam;
- the enabled modules, such as Preparation, Review, AMC and Results;
- the Review progress when Review is enabled;
- direct action buttons.

The available action buttons depend on the user's permissions and on the modules enabled for the exam. A manager can usually open **Info**, **Prepare** and **AMC**. Reviewers can open **Review**. Users with results access can open **Results**.

Filters and search
------------------

Use the buttons above the exam table to filter exams by access type:

- **All** shows all visible exams;
- **Manage** shows exams where the user has management access;
- **Review** shows exams where the user can review open questions;
- **Results** shows exams where the user can view results.

The search field filters the visible table by exam code, exam name, role and enabled modules. If the user has more than the configured dashboard limit, only the most recent exams are displayed.

Review progress
---------------

When Review is enabled, the dashboard displays the number of reviewed pages and the total number of pages. The progress bar turns green when all pages are reviewed.

To do
-----

The **To do** panel lists the most important pending actions for the current user.

For users with management access, it can include:

- configure Review pages groups;
- assign reviewers;
- upload Review scans;
- create a scale for Results;
- import result data;
- generate statistics.

For reviewers, it can include:

- continue a pages group that is not fully reviewed;
- check an exam where Review access is currently blocked;
- check an exam where no pages group has been assigned yet.

Shortcuts
---------

The **Shortcuts** panel gives quick access to common tools:

- **Open exam** to browse the exam list;
- **Room plan** to generate room plans;
- **Students CSV generator** to prepare student CSV files;
- **Documentation** to open this documentation.

Superusers also see shortcuts to **Create exam** and **Admin**, and a table with users' last connection times.

Sidebar navigation
------------------

The left sidebar always contains a **DASHBOARD** entry for authenticated users. Once an exam is selected, the sidebar displays only the modules that are enabled for that exam and allowed for the current user.

The Review menu contains:

- **Review** for the Review summary and correction screens;
- **Settings** for pages groups, reviewers and grading schemes;
- **Upload scans** to import scans for online review;
- **Export marked scans** to export the reviewed scans.

The AMC menu contains **AMC** and **Import data**. When Results and Statistics are enabled, the sidebar also exposes **Results**, **Statistics**, **Import data** and **Export results**.
