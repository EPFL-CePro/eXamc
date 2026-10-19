import 'vite/modulepreload-polyfill';

import {initPrepStudentsTable} from "./prep-students-table.ts";
import {initPrepStudentEdit} from "./prep-student-edit.ts";
import {initSeatsAssign} from "./seats-assign.ts";
import {initStudentsApiImport, initStudentsFileImport} from "./students-import.ts";
import {initStudentsOrder} from "./students-order.ts";
import {initStudentsPanels} from "./students-panels.ts";

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
        summary: document.querySelector<HTMLElement>("#prepStudentsSummary"),
    });

    const toolbar = document.querySelector<HTMLElement>(".prep-students-toolbar");
    if (toolbar) {
        const {openPanel, hasStoredPanel} = initStudentsPanels(toolbar);
        // An exam without students: show the import first
        if (!hasStoredPanel) {
            table.one("xhr", (_event, _settings, json) => {
                if (!(json as {data?: unknown[]} | null)?.data?.length) openPanel("get");
            });
        }
    }

    const modalElement = document.querySelector<HTMLElement>("#prepStudentEditModal");
    if (modalElement) {
        initPrepStudentEdit({table, tableElement, apiUrl, modalElement});
    }

    const resultElement = document.querySelector<HTMLElement>("#importStudentsResult");
    if (!resultElement) return;

    const fileButtons = [...document.querySelectorAll<HTMLButtonElement>(".import-students-from-xlsx")];
    const fileInput = document.querySelector<HTMLInputElement>("#importStudentsFile");
    if (fileButtons.length && fileInput) {
        initStudentsFileImport({buttons: fileButtons, fileInput, resultElement, table});
    }

    const apiButton = document.querySelector<HTMLButtonElement>("#importStudentsFromAPI");
    if (apiButton) {
        initStudentsApiImport({button: apiButton, resultElement, table});
    }

    const reorderForm = document.querySelector<HTMLFormElement>("#reorderStudentsForm");
    if (reorderForm) {
        initStudentsOrder({form: reorderForm, resultElement, table});
    }

    const seatsForm = document.querySelector<HTMLFormElement>("#assignSeatsForm");
    const seatsPreview = document.querySelector<HTMLElement>("#assignSeatsPreview");
    if (seatsForm && seatsPreview) {
        initSeatsAssign({form: seatsForm, previewElement: seatsPreview, resultElement, table});
    }
});
