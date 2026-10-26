import 'vite/modulepreload-polyfill';

import {initPrepStudentsTable} from "./prep-students-table.ts";
import {initPrepStudentEdit} from "./prep-student-edit.ts";
import {initSeatsAssign} from "./seats-assign.ts";
import {initStudentsApiImport, initStudentsFileImport} from "./students-import.ts";
import {initStudentsOrder} from "./students-order.ts";
import { byId, requireData } from '@examc/helpers/dom.ts';

document.addEventListener("DOMContentLoaded", () => {
    const tableEl = byId<HTMLTableElement>("prep-students-dt");
    const prepStudentEditModalEl = byId("prepStudentEditModal");
    const importStudentsResultEl = byId("importStudentsResult");
    const importStudentsFileEl = byId<HTMLInputElement>("importStudentsFile");
    const importStudentsFromApiEl = byId<HTMLButtonElement>("importStudentsFromAPI");
    const reorderStudentsFormEl = byId<HTMLFormElement>("reorderStudentsForm");
    const assignSeatsFormEl = byId<HTMLFormElement>("assignSeatsForm");
    const assignSeatsPreviewEl = byId<HTMLElement>("assignSeatsPreview");

    const fileButtons = [...document.querySelectorAll<HTMLButtonElement>(".import-students-from-xlsx")];

    const apiUrl = requireData(tableEl, "apiUrl");

    
    const table = initPrepStudentsTable({
        tableElement: tableEl,
        apiUrl,
        toCorrectBanner: document.querySelector<HTMLElement>("#prepStudentsToCorrect"),
        summary: document.querySelector<HTMLElement>("#prepStudentsSummary"),
    });

    
    if (fileButtons.length > 0) {
        initStudentsFileImport({ buttons: fileButtons, fileInput: importStudentsFileEl, resultElement: importStudentsResultEl, table });
    }

    initPrepStudentEdit({table, tableElement: tableEl, apiUrl, modalElement: prepStudentEditModalEl });
    initStudentsApiImport({button: importStudentsFromApiEl, resultElement: importStudentsResultEl, table});
    initStudentsOrder({form: reorderStudentsFormEl, resultElement: importStudentsResultEl, table});
    initSeatsAssign({form: assignSeatsFormEl, previewElement: assignSeatsPreviewEl, resultElement: importStudentsResultEl, table});
});
