import { ConfirmModal } from "@examc/modals";

import { EXAM_PK, Selectors, URLS } from "./config.ts";
import { showSaveToast } from "./save-toast.ts";
import { type AjaxCallbacks, ajaxGet, ajaxPost, getElement, hideModal, showModal } from "./ajax.ts";

interface ScoringParams {
    exam_pk: string;
    prep_section: string;
    prep_question: string;
    prep_answer: string;
}

interface ScoringResponse {
    success?: boolean;
    message?: string;
    html?: string;
}

function setBody(html: string): void {
    const body = getElement(Selectors.scoringModalBody);
    if (body) body.innerHTML = html;
}

function renderError(message?: string): void {
    setBody(`<div class="alert alert-danger mb-0">${message || "Unable to load formulas."}</div>`);
}

function buildParams(button: HTMLElement): ScoringParams {
    return {
        exam_pk: button.dataset["examPk"] || EXAM_PK || "",
        prep_section: button.dataset["prepSection"] || "",
        prep_question: button.dataset["prepQuestion"] || "",
        prep_answer: button.dataset["prepAnswer"] || "",
    };
}

function open(params: ScoringParams, spinner: AjaxCallbacks<string>["spinner"] = true): void {
    if (!URLS.scoringFormulasModal) {
        console.warn("[preparation] Missing scoringFormulasModal URL");
        renderError("Configuration error: missing modal URL.");
        showModal(Selectors.scoringModal);
        return;
    }

    if (!params.exam_pk) {
        renderError("Missing exam_pk.");
        showModal(Selectors.scoringModal);
        return;
    }

    ajaxGet<string>(URLS.scoringFormulasModal, params, {
        spinner,
        success: (html) => {
            setBody(html);
            showModal(Selectors.scoringModal);
        },
        error: (xhr) => {
            console.error("[preparation] open scoring formulas modal failed:", xhr);
            renderError("Unable to load formulas.");
            showModal(Selectors.scoringModal);
        },
    });
}

function submit(form: HTMLFormElement): void {
    // Saving rewrites the LaTeX files: the saving overlay shows it above the dialog, which stays open until the answer
    ajaxPost<ScoringResponse>(form.action, $(form).serialize(), {
        spinner: "saving",
        success: (response) => {
            if (response.success) {
                hideModal(Selectors.scoringModal);

                if (response.message) {
                    showSaveToast(response.message, false);
                }
                return;
            }

            if (response.html) {
                setBody(response.html);
                return;
            }

            renderError(response.message || "Unable to save formulas.");
        },
        error: (xhr) => {
            console.error("[preparation] save scoring formulas failed:", xhr);

            const response = xhr.responseJSON as ScoringResponse | undefined;
            if (response && response.html) {
                setBody(response.html);
                return;
            }

            renderError("An error occurred while saving formulas.");
        },
    });
}

function updateRowIndexes(): void {
    document.querySelectorAll("#scoringFormulasTableBody .scoring-formula-row").forEach((row, index) => {
        const indexCell = row.querySelector(".scoring-row-index");
        if (!indexCell) return;

        const hiddenIdInput = indexCell.querySelector('input[type="hidden"]');
        if (indexCell.firstChild) indexCell.firstChild.textContent = (index + 1) + " ";

        if (hiddenIdInput) {
            indexCell.appendChild(hiddenIdInput);
        }
    });
}

function removeEmptyMessageRow(): void {
    document.querySelector(".no-scoring-formulas-row")?.remove();
}

function addRow(): void {
    const template = document.getElementById("emptyScoringFormulaRowTemplate");
    const tbody = document.getElementById("scoringFormulasTableBody");
    const totalFormsInput = document.getElementById("id_form-TOTAL_FORMS") as HTMLInputElement | null;

    if (!template || !tbody || !totalFormsInput) {
        console.warn("[preparation] Missing template, tbody, or TOTAL_FORMS input.");
        return;
    }

    const formIndex = parseInt(totalFormsInput.value, 10);
    let html = template.innerHTML.replace(/__prefix__/g, String(formIndex));
    html = html.replace(/__index__/g, String(formIndex + 1));

    removeEmptyMessageRow();
    tbody.insertAdjacentHTML("beforeend", html);

    totalFormsInput.value = String(formIndex + 1);
    updateRowIndexes();
}

function removeUnsavedRow(button: HTMLElement): void {
    const row = button.closest(".scoring-formula-row");
    const tbody = document.getElementById("scoringFormulasTableBody");
    const totalFormsInput = document.getElementById("id_form-TOTAL_FORMS") as HTMLInputElement | null;

    if (!row || !tbody || !totalFormsInput) return;

    row.remove();

    const rows = tbody.querySelectorAll(".scoring-formula-row");
    totalFormsInput.value = String(rows.length);

    rows.forEach((currentRow, index) => {
        currentRow.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | HTMLLabelElement>("input, select, textarea, label").forEach((el) => {
            if ("name" in el && el.name) {
                el.name = el.name.replace(/form-\d+-/g, `form-${index}-`);
            }
            if (el.id) {
                el.id = el.id.replace(/id_form-\d+-/g, `id_form-${index}-`);
            }
            if ("htmlFor" in el && el.htmlFor) {
                el.htmlFor = el.htmlFor.replace(/id_form-\d+-/g, `id_form-${index}-`);
            }
        });
    });

    updateRowIndexes();

    if (!tbody.querySelector(".scoring-formula-row")) {
        tbody.innerHTML = `
        <tr class="no-scoring-formulas-row">
          <td colspan="4" class="text-center">No formulas found.</td>
        </tr>
      `;
    }
}

function reloadFromCurrentForm(): void {
    const form = document.getElementById("scoringFormulasForm");
    if (!form) return;

    const value = (name: string) => form.querySelector<HTMLInputElement>(`input[name="${name}"]`)?.value || "";

    // The dialog is already open: no spinner behind it
    open({
        exam_pk: EXAM_PK || "",
        prep_section: value("prep_section"),
        prep_question: value("prep_question"),
        prep_answer: value("prep_answer"),
    }, false);
}

async function deleteSavedRow(deleteUrl: string | undefined): Promise<void> {
    if (!deleteUrl) return;

    const confirmed = await ConfirmModal.confirm({
        title: "Delete scoring formula",
        message: "Delete this scoring formula? This cannot be undone.",
        confirmLabel: "Yes, delete",
        confirmClass: "btn-danger",
    });
    if (!confirmed) return;

    ajaxPost<ScoringResponse>(deleteUrl, {}, {
        spinner: "saving",
        success: (response) => {
            if (response.success) {
                reloadFromCurrentForm();
                return;
            }

            renderError(response.message || "Unable to delete formula.");
        },
        error: (xhr) => {
            console.error("[preparation] delete scoring formula failed:", xhr);
            renderError("An error occurred while deleting formula.");
        },
    });
}

export function initScoringFormulas(): void {
    document.addEventListener("click", (event) => {
        const target = event.target as Element;

        const addButton = target.closest("#addScoringFormulaRow");
        if (addButton) {
            event.preventDefault();
            addRow();
            return;
        }

        const removeUnsavedButton = target.closest<HTMLElement>(".remove-scoring-formula-row");
        if (removeUnsavedButton) {
            event.preventDefault();
            removeUnsavedRow(removeUnsavedButton);
            return;
        }

        const deleteSavedButton = target.closest<HTMLElement>(".delete-scoring-formula-row");
        if (deleteSavedButton) {
            event.preventDefault();
            void deleteSavedRow(deleteSavedButton.dataset["deleteUrl"]);
            return;
        }

        const button = target.closest<HTMLElement>(Selectors.openScoringModalBtn);
        if (!button) return;

        event.preventDefault();
        open(buildParams(button));
    });

    document.addEventListener("submit", (event) => {
        const form = (event.target as Element).closest<HTMLFormElement>(Selectors.scoringForm);
        if (!form) return;

        event.preventDefault();
        submit(form);
    });
}
