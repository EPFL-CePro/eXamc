import type { Api } from 'datatables.net-dt';

import { confirmDialog } from '@examc/helpers/confirm-dialog';
import { withLoadingModal } from '@examc/helpers/loading-modal';

type ImportResponse = {
    imported?: number;
    replaced?: number;
    warnings?: string[];
    errors?: string[];
};


function showResult(resultElement: HTMLElement, kind: "success" | "warning" | "danger", title: string,
                    details: string[] = []): void {
    resultElement.replaceChildren();
    resultElement.classList.remove("alert-success", "alert-warning", "alert-danger");
    resultElement.classList.add(`alert-${kind}`);

    // Texts are set with textContent: the errors quote the file content
    const heading = document.createElement("div");
    heading.className = "fw-bold";
    heading.textContent = title;
    resultElement.append(heading);

    if (details.length) {
        const list = document.createElement("ul");
        list.className = "mb-0 mt-1";
        for (const detail of details) {
            const item = document.createElement("li");
            item.textContent = detail;
            list.append(item);
        }
        resultElement.append(list);
    }
    resultElement.hidden = false;
}

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
    const { importUrl, csrfToken } = button.dataset;
    if (!importUrl || !csrfToken) {
        console.error(`#${button.id} missing data-import-url or data-csrf-token attribute`);
        return;
    }

    const currentCount = table.rows().count();
    if (currentCount > 0) {
        const confirmed = await confirmDialog({
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
        const { response, data } = await withLoadingModal(async () => {
            const response = await fetch(importUrl, {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken },
                body: body ?? null,
            });
            const data: ImportResponse = await response.json().catch(() => ({}));
            return { response, data };
        });

        if (response.ok) {
            const warnings = data.warnings ?? [];
            showResult(resultElement, warnings.length ? "warning" : "success",
                `${data.imported} students imported from ${source}.`, warnings);
            table.ajax.reload();
        } else {
            showResult(resultElement, "danger", `The students from ${source} were not imported, nothing was changed:`,
                data.errors ?? [`Server error (${response.status}).`]);
        }
    } catch (error) {
        console.error("Students import failed", error);
        showResult(resultElement, "danger", "The request could not be sent: please check your connection and try again.");
    } finally {
        button.disabled = false;
    }
}

/**
 * "Import from Excel" button: picks an .xlsx file, sent to the server, which replaces the exam students.
 */
export function initStudentsFileImport(options: {
    button: HTMLButtonElement;
    fileInput: HTMLInputElement;
    resultElement: HTMLElement;
    table: Api;
}): void {
    const { button, fileInput, resultElement, table } = options;

    button.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", () => {
        const file = fileInput.files?.[0];
        // Allows choosing the same file again after fixing it
        fileInput.value = "";
        if (!file) return;

        const body = new FormData();
        body.append("students_file", file);
        void runImport({ button, resultElement, table, source: `"${file.name}"`, body });
    });
}

/**
 * "Import from API" button: the server replaces the exam students by those enrolled in the course in IS-Academia.
 */
export function initStudentsApiImport(options: {
    button: HTMLButtonElement;
    resultElement: HTMLElement;
    table: Api;
}): void {
    const { button, resultElement, table } = options;
    button.addEventListener("click", () => void runImport({ button, resultElement, table, source: "IS-Academia" }));
}
