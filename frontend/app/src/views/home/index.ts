import 'vite/modulepreload-polyfill';

import 'datatables.net-dt/css/dataTables.dataTables.min.css';

import {initExamSelectTable} from "./examSelectTable";
import {lastConnectedUsersTable} from "./lastConnectedUsersTable.ts";
import "./dashboard.scss";
import {byId} from "@examc/helpers/dom.ts";


/**
 * Initializes the exam select table and last user connected after the DOM has loaded.
 */
document.addEventListener("DOMContentLoaded", () => {
    // exam select table
    const examTableElement = byId<HTMLTableElement>("dashboard-exam-table");
    const examApiUrl = examTableElement.dataset.apiUrl;

    if (!examApiUrl) {
        console.error("Exam table missing data-api-url attribute");
        return;
    }
    initExamSelectTable({ tableElement: examTableElement, apiUrl: examApiUrl });

    // last connected users table
    const usersTableElement = document.querySelector<HTMLTableElement>("#dashboard-last-connected-users-table");
    const usersConnectedApiUrl = usersTableElement?.dataset.apiUrl;
    if (!usersConnectedApiUrl) {
        console.error("Connected users table missing data-api-url attribute");
        return;
    }

    if (!examTableElement || !usersTableElement) return;

    lastConnectedUsersTable({ tableElement: usersTableElement, apiUrl: usersConnectedApiUrl });
});
