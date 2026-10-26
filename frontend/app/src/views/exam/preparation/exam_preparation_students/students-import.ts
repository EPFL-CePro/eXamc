import type { Api } from 'datatables.net-bs5';

import { postForm } from '@examc/helpers/http.ts';
import { ConfirmModal, LoadingModal } from '@examc/modals';

import { showFailure, showResult } from "./result.ts";

type ImportResponse = {
    imported?: number;
    replaced?: number;
    warnings?: string[];
};

/**
 * Asks before replacing the current students, sends the import request, shows the result and reloads the table.
 * `source` names what is imported in the messages, e.g. "students.xlsx" or "IS-Academia".
 */
async function runImport(options: {
    button: HTMLButtonElement;
    resultElement: HTMLElement;
    table: Api;
    source: string;
    body?: FormData;
}): Promise<void> {
    const { button, resultElement, table, source, body } = options;
    const { importUrl } = button.dataset;
    if (!importUrl) {
        console.error(`#${button.id} missing data-import-url attribute`);
        return;
    }

    const currentCount = table.rows().count();
    if (currentCount > 0) {
        const confirmed = await ConfirmModal.confirm({
            title: "Replace the students",
            warning: `The ${currentCount} students of this exam will be deleted.`,
            message: `Replace them by the students from ${source}?`,
            confirmLabel: "Yes, replace",
            confirmClass: "btn-danger",
        });
        if (!confirmed) return;
    }

    button.disabled = true;
    try {
        const data = await new LoadingModal(
            async () => (await postForm(importUrl, {}, body)).json() as Promise<ImportResponse>,
        ).result;

        const warnings = data.warnings ?? [];
        showResult(resultElement, warnings.length ? "warning" : "success",
            `${data.imported} students imported from ${source}.`, warnings);
        table.ajax.reload();
    } catch (error) {
        showFailure(resultElement, error, `The students from ${source} were not imported, nothing was changed:`);
    } finally {
        button.disabled = false;
    }
}

/**
 * "Import the file" buttons (in "Get the students" and "Arrange them"): pick an .xlsx file, sent to the server,
 * which replaces the exam students.
 */
export function initStudentsFileImport(options: {
    buttons: HTMLButtonElement[];
    fileInput: HTMLInputElement;
    resultElement: HTMLElement;
    table: Api;
}): void {
    const { buttons, fileInput, resultElement, table } = options;
    // The button that opened the file picker, disabled during its import
    let clickedButton: HTMLButtonElement | null = null;

    for (const button of buttons) {
        button.addEventListener("click", () => {
            clickedButton = button;
            fileInput.click();
        });
    }

    fileInput.addEventListener("change", () => {
        const file = fileInput.files?.[0];
        // Allows choosing the same file again after fixing it
        fileInput.value = "";
        if (!file || !clickedButton) return;

        const body = new FormData();
        body.append("students_file", file);
        void runImport({ button: clickedButton, resultElement, table, source: `"${file.name}"`, body });
    });
}

/**
 * "Import from IS-Academia" button: the server replaces the exam students by those enrolled in the course in IS-Academia.
 */
export function initStudentsApiImport(options: {
    button: HTMLButtonElement;
    resultElement: HTMLElement;
    table: Api;
}): void {
    const { button, resultElement, table } = options;
    button.addEventListener("click", () => void runImport({ button, resultElement, table, source: "IS-Academia" }));
}
