import type { Api } from 'datatables.net-dt';

import { confirmDialog } from '@examc/helpers/confirm-dialog';

import { showResult } from "./studentsImport.ts";

type ReorderResponse = {
    reordered?: number;
    errors?: string[];
};

/**
 * "Order the students" form: the server gives the IDs (copy numbers) 1, 2, 3... in the chosen order
 * (see services/student/prep_order.py), then the table is reloaded.
 */
export function initStudentsOrder(options: {
    form: HTMLFormElement;
    resultElement: HTMLElement;
    table: Api;
}): void {
    const { form, resultElement, table } = options;
    const { reorderUrl, csrfToken } = form.dataset;
    if (!reorderUrl || !csrfToken) {
        console.error("#reorderStudentsForm missing data-reorder-url or data-csrf-token attribute");
        return;
    }
    const select = form.querySelector<HTMLSelectElement>("select[name=order]")!;
    const submitButton = form.querySelector<HTMLButtonElement>("button[type=submit]")!;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const count = table.rows().count();
        if (!count) {
            showResult(resultElement, "warning", "There are no students to renumber: import them first.");
            return;
        }

        const orderLabel = select.selectedOptions[0]?.textContent?.trim().toLowerCase() ?? select.value;
        const confirmed = await confirmDialog({
            title: "Renumber the students",
            warning: `The IDs (copy numbers) of the ${count} students will change. Rooms and seats do not change.`,
            message: `Renumber them ${orderLabel}?`,
            confirmLabel: "Yes, renumber",
            confirmClass: "btn-danger",
        });
        if (!confirmed) return;

        submitButton.disabled = true;
        try {
            const response = await fetch(reorderUrl, {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken },
                body: new FormData(form),
            });
            const data: ReorderResponse = await response.json().catch(() => ({}));

            if (response.ok) {
                showResult(resultElement, "success", `${data.reordered} students renumbered ${orderLabel}.`);
                table.ajax.reload();
            } else {
                showResult(resultElement, "danger", "The students were not renumbered, nothing was changed:",
                    data.errors ?? [`Server error (${response.status}).`]);
            }
        } catch (error) {
            console.error("Students reorder failed", error);
            showResult(resultElement, "danger",
                "The request could not be sent: please check your connection and try again.");
        } finally {
            submitButton.disabled = false;
        }
    });
}
