import 'vite/modulepreload-polyfill';

import {initUserSelectTable} from "./userSelectTable";
import {byId} from "@examc/helpers/dom.ts";


/**
 * Initializes the exam select table after the DOM has loaded.
 */
document.addEventListener("DOMContentLoaded", () => {
    const tableElement = byId<HTMLTableElement>("impersonation-users-table");

    const apiUrl = tableElement.dataset.apiUrl;

    if (!apiUrl) {
        console.error("Exam table missing data-api-url attribute");
        return;
    }

    initUserSelectTable({ tableElement, apiUrl });
});
