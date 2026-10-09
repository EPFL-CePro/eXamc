import type { Api } from 'datatables.net-dt';

import { getPageBootstrap } from '@examc/helpers/page-bootstrap';

import type { PrepStudentRow } from "./prepStudentsTable.ts";

const FIELDS = ["copy_no", "sciper", "last_name", "first_name", "email", "section", "room", "seat"] as const;

type ErrorResponse = {
    errors?: string[];
    detail?: string;
    [field: string]: unknown;
};


// DRF errors: {"errors": [...]}, {"detail": "..."} or {"field": ["message"]}
function errorMessages(data: ErrorResponse, status: number): string[] {
    if (Array.isArray(data.errors)) return data.errors;
    if (typeof data.detail === "string") return [data.detail];

    const messages = Object.entries(data).flatMap(([field, value]) =>
        (Array.isArray(value) ? value : [value]).map((message) => `${field.replace("_", " ")}: ${message}`));
    return messages.length ? messages : [`Server error (${status}).`];
}

/**
 * Pencil button of the students table: edits a student in #prepStudentEditModal and saves it with
 * PATCH <apiUrl><id>/ (see PrepStudentViewSet.partial_update), then reloads the table.
 */
export function initPrepStudentEdit(options: {
    table: Api;
    tableElement: HTMLTableElement;
    apiUrl: string;
    modalElement: HTMLElement;
}): void {
    const { table, tableElement, apiUrl, modalElement } = options;
    const csrfToken = tableElement.dataset.csrfToken ?? "";
    const form = modalElement.querySelector<HTMLFormElement>("form")!;
    const errorsElement = modalElement.querySelector<HTMLElement>("#prepStudentEditErrors")!;
    const notFoundElement = modalElement.querySelector<HTMLElement>("#prepStudentEditNotFound")!;
    const saveButton = modalElement.querySelector<HTMLButtonElement>("#prepStudentEditSave")!;
    const modal = getPageBootstrap().Modal.getOrCreateInstance(modalElement);
    let editedId: number | null = null;

    const input = (field: typeof FIELDS[number]) => form.elements.namedItem(field) as HTMLInputElement;

    function showErrors(messages: string[]): void {
        errorsElement.replaceChildren(...messages.map((message) => {
            const line = document.createElement("div");
            line.textContent = message;
            return line;
        }));
        errorsElement.hidden = messages.length === 0;
    }

    // Delegated: the rows are redrawn by DataTables
    tableElement.addEventListener("click", (event) => {
        const button = (event.target as Element).closest<HTMLButtonElement>(".prep-student-edit");
        const row = button && table.row(button.closest("tr")!).data() as PrepStudentRow | undefined;
        if (!row) return;

        editedId = row.id;
        for (const field of FIELDS) {
            input(field).value = String(row[field] ?? "");
        }
        notFoundElement.hidden = !row.needs_correction;
        showErrors([]);
        modal.show();
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (editedId === null) return;

        const body = Object.fromEntries(FIELDS.map((field) => [field, input(field).value.trim()]));

        saveButton.disabled = true;
        try {
            const response = await fetch(`${apiUrl}${editedId}/`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify(body),
            });

            if (response.ok) {
                modal.hide();
                table.ajax.reload();
            } else {
                const data: ErrorResponse = await response.json().catch(() => ({}));
                showErrors(errorMessages(data, response.status));
            }
        } catch (error) {
            console.error("Student update failed", error);
            showErrors(["The request could not be sent: please check your connection and try again."]);
        } finally {
            saveButton.disabled = false;
        }
    });
}
