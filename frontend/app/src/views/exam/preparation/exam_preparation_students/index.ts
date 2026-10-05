import 'vite/modulepreload-polyfill';

import {initPrepStudentsTable} from "./prepStudentsTable.ts";
import {initPrepStudentEdit} from "./prepStudentEdit.ts";
import {initStudentsApiImport, initStudentsFileImport} from "./studentsImport.ts";

document.addEventListener("DOMContentLoaded", () => {
    const tableElement = document.querySelector<HTMLTableElement>("#prep-students-dt");
    if (!tableElement) return;

    const {apiUrl} = tableElement.dataset;
    if (!apiUrl) {
        console.error("Prep students table missing data-api-url attribute");
        return;
    }
    const table = initPrepStudentsTable({
        tableElement,
        apiUrl,
        toCorrectBanner: document.querySelector<HTMLElement>("#prepStudentsToCorrect"),
    });

    const modalElement = document.querySelector<HTMLElement>("#prepStudentEditModal");
    if (modalElement) {
        initPrepStudentEdit({table, tableElement, apiUrl, modalElement});
    }

    const resultElement = document.querySelector<HTMLElement>("#importStudentsResult");
    if (!resultElement) return;

    const fileButton = document.querySelector<HTMLButtonElement>("#importStudentsFromXlsx");
    const fileInput = document.querySelector<HTMLInputElement>("#importStudentsFile");
    if (fileButton && fileInput) {
        initStudentsFileImport({button: fileButton, fileInput, resultElement, table});
    }

    const apiButton = document.querySelector<HTMLButtonElement>("#importStudentsFromAPI");
    if (apiButton) {
        initStudentsApiImport({button: apiButton, resultElement, table});
    }
});
