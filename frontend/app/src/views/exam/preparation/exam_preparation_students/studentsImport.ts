import type { Api } from 'datatables.net-dt';

import { confirmDialog } from '@examc/helpers/confirm-dialog';

type ImportResponse = {
    imported?: number;
    replaced?: number;
    errors?: string[];
};


function showResult(resultElement: HTMLElement, kind: "success" | "danger", title: string, details: string[] = []): void {
    resultElement.replaceChildren();
    resultElement.classList.remove("alert-success", "alert-danger");
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
 * "Import from Excel" button: picks an .xlsx file, sends it to the server, which replaces the exam students,
 * then reloads the table.
 */
export function initStudentsImport(options: {
    button: HTMLButtonElement;
    fileInput: HTMLInputElement;
    resultElement: HTMLElement;
    table: Api;
}): void {
    const { button, fileInput, resultElement, table } = options;
    const { importUrl, csrfToken } = button.dataset;
    if (!importUrl || !csrfToken) {
        console.error("Import button missing data-import-url or data-csrf-token attribute");
        return;
    }

    button.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", async () => {
        const file = fileInput.files?.[0];
        // Allows choosing the same file again after fixing it
        fileInput.value = "";
        if (!file) return;

        const currentCount = table.page.info().recordsTotal;
        if (currentCount > 0) {
            const confirmed = await confirmDialog({
                title: "Replace the students",
                warning: `The ${currentCount} students of this exam will be deleted.`,
                message: `Replace them by the students of "${file.name}"?`,
                confirmLabel: "Yes, replace",
                confirmClass: "btn-danger",
            });
            if (!confirmed) return;
        }

        const body = new FormData();
        body.append("students_file", file);

        button.disabled = true;
        try {
            const response = await fetch(importUrl, {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken },
                body,
            });
            const data: ImportResponse = await response.json().catch(() => ({}));

            if (response.ok) {
                showResult(resultElement, "success", `${data.imported} students imported from "${file.name}".`);
                table.ajax.reload();
            } else {
                showResult(resultElement, "danger", `"${file.name}" was not imported, nothing was changed:`,
                    data.errors ?? [`Server error (${response.status}).`]);
            }
        } catch (error) {
            console.error("Students import failed", error);
            showResult(resultElement, "danger", "The file could not be sent: please check your connection and try again.");
        } finally {
            button.disabled = false;
        }
    });
}
