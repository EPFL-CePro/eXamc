import 'vite/modulepreload-polyfill';

import {initUserSelectTable} from "./userSelectTable";


/**
 * Initializes the exam select table after the DOM has loaded.
 */
document.addEventListener("DOMContentLoaded", () => {
    const tableElement = document.querySelector<HTMLTableElement>("#impersonation-users-table");
    if (!tableElement) return;

    const apiUrl = tableElement.dataset.apiUrl;

    if (!apiUrl) {
        console.error("Exam table missing data-api-url attribute");
        return;
    }

    initUserSelectTable({ tableElement, apiUrl });
});
