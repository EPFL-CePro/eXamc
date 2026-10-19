import type { Api } from 'datatables.net-dt';

import { postForm } from '@examc/helpers/http.ts';
import { ConfirmModal } from '@examc/modals';

import { showFailure, showResult } from "./result.ts";

type ReorderResponse = {
    reordered?: number;
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
    const { reorderUrl } = form.dataset;
    if (!reorderUrl) {
        console.error("#reorderStudentsForm missing data-reorder-url attribute");
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
        const confirmed = await ConfirmModal.confirm({
            title: "Renumber the students",
            warning: `The IDs (copy numbers) of the ${count} students will change. Rooms and seats do not change.`,
            message: `Renumber them ${orderLabel}?`,
            confirmLabel: "Yes, renumber",
            confirmClass: "btn-danger",
        });
        if (!confirmed) return;

        submitButton.disabled = true;
        try {
            const data = await (await postForm(reorderUrl, {}, new FormData(form))).json() as ReorderResponse;
            showResult(resultElement, "success", `${data.reordered} students renumbered ${orderLabel}.`);
            table.ajax.reload();
        } catch (error) {
            showFailure(resultElement, error, "The students were not renumbered, nothing was changed:");
        } finally {
            submitButton.disabled = false;
        }
    });
}
