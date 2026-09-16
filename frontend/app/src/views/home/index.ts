import 'vite/modulepreload-polyfill';

import "./main.scss";
import {initExamSelectTable} from "./examSelectTable";


/**
 * Initializes the exam select table after the DOM has loaded.
 */
document.addEventListener("DOMContentLoaded", () => {
    const tableElement = document.querySelector<HTMLTableElement>("#dashboard-exam-table");
    if (!tableElement) return;

    const apiUrl = tableElement.dataset.apiUrl;

    if (!apiUrl) {
        console.error("Exam table missing data-api-url attribute");
        return;
    }

    initExamSelectTable({ tableElement, apiUrl });
});