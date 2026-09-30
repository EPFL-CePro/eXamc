import 'vite/modulepreload-polyfill';

import {initStudentsTable} from "./studentSelectTable.ts";
import {byId} from "@examc/helpers/dom.ts";

document.addEventListener("DOMContentLoaded", () => {
    const tableElement = byId<HTMLTableElement>("students-dt");

    if (tableElement) {
        const {apiUrl, csrfToken} = tableElement.dataset;

        if (apiUrl && csrfToken) {
            initStudentsTable({tableElement, apiUrl, csrfToken});
        } else {
            console.error("Students table missing data-api-url or data-csrf-token attribute");
        }
    }
});

