import 'vite/modulepreload-polyfill';

import "./main.scss";
import {initStudentsTable} from "./studentSelectTable.ts";

document.addEventListener("DOMContentLoaded", () => {
    const tableElement = document.querySelector<HTMLTableElement>("#students-dt");
    if (!tableElement) return;

    if (tableElement) {
        const {apiUrl, csrfToken} = tableElement.dataset;

        if (apiUrl && csrfToken) {
            initStudentsTable({tableElement, apiUrl, csrfToken});
        } else {
            console.error("Students table missing data-api-url or data-csrf-token attribute");
        }
    }
});

