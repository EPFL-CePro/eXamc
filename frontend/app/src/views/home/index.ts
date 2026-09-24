import 'vite/modulepreload-polyfill';

import 'datatables.net-dt/css/dataTables.dataTables.min.css';

import {initExamSelectTable} from "./examSelectTable";
import {lastConnectedUsersTable} from "./lastConnectedUsersTable.ts";
import "./dashboard.scss";


/**
 * Initializes the exam select table and last user connected after the DOM has loaded.
 */
document.addEventListener("DOMContentLoaded", () => {
    const examTableElement = document.querySelector<HTMLTableElement>("#dashboard-exam-table");
    const usersTableElement = document.querySelector<HTMLTableElement>("#dashboard-last-connected-users-table");

    if (!examTableElement || !usersTableElement) return;

    const examApiUrl = examTableElement.dataset.apiUrl;

    if (!examApiUrl) {
        console.error("Exam table missing data-api-url attribute");
        return;
    }


    initExamSelectTable({ tableElement: examTableElement, apiUrl: examApiUrl });
    lastConnectedUsersTable({ tableElement: usersTableElement });
});
