import { describeFailure, failureJson, getJson, getText, postForm, postJson } from "@examc/helpers/http.ts";
import { byId, sleep } from "@examc/helpers/dom.ts";
import { ConfirmModal, LocalModal } from "@examc/modals";

import { EXAM_PK, Selectors, URLS } from "./config.ts";
import { showSaveToast } from "./save-toast.ts";
import { getElement, type Spinner, withQuery, withSpinner } from "./ajax.ts";

type ScoringParams = {
    exam_pk: string;
    prep_section: string;
    prep_question: string;
    prep_answer: string;
};

interface ScoringResponse {
    success?: boolean;
    message?: string;
    html?: string;
    /** The update of the marking scale of AMC that follows a change on a final exam (see followScoringUpdate). */
    scoring_update?: { job_id: number; status_url: string };
}

interface ScoringUpdateStatus {
    status: "pending" | "running" | "success" | "error";
    error?: string;
    warnings?: string[];
}

const SCORING_UPDATE_POLL_MS = 2000;
// AMC compiles the copies again: about a minute for 230 copies, the server gives up on a job after 30 minutes
const SCORING_UPDATE_MAX_POLLS = 900;

/**
 * A change of the formulas of a final exam makes AMC update its marking scale in the background (the server answers
 * with the job): tells when it is done, or why it failed.
 */
async function followScoringUpdate(statusUrl: string): Promise<void> {
    showSaveToast("Formulas saved. AMC is updating its marking scale...", false);

    for (let poll = 0; poll < SCORING_UPDATE_MAX_POLLS; poll++) {
        await sleep(SCORING_UPDATE_POLL_MS);

        let state: ScoringUpdateStatus;
        try {
            state = await getJson<ScoringUpdateStatus>(statusUrl);
        } catch (error) {
            console.error("[preparation] scoring update status failed:", error);
            continue;
        }

        if (state.status === "success") {
            showSaveToast("The marking scale of AMC is updated.", false);
            return;
        }
        if (state.status === "error") {
            await ConfirmModal.confirm({
                title: "The marking scale of AMC was not updated",
                message: state.error || "AMC failed to update its marking scale.",
                warning: "The formulas are saved, but the marks of AMC still use the previous ones.",
                confirmLabel: "OK",
                cancelLabel: "Close",
                confirmClass: "btn-dark",
            });
            return;
        }
    }
    showSaveToast("The update of the marking scale of AMC takes longer than expected.", true);
}

// The server refuses a change while AMC works on the project (403): its reason is for the user
function refusedReason(error: unknown): string | null {
    const failure = describeFailure(error);
    return failure.status === 403 && failure.text ? failure.text : null;
}

/**
 * Text next to the Scoring button of each question and answer (the formula applied, with its level), and frame in the
 * Scoring button of each level (what it has formulas for), by kind of level ("exam", "section", "question", "answer")
 * and id: only the buttons that have one.
 */
interface ScoringInfos {
    questions: Record<string, string>;
    answers: Record<string, string>;
    badges: Record<string, Record<string, string>>;
}

// The formulas of the exam, sections and questions change what the other questions apply: all the texts are read again
async function refreshScoringInfos(): Promise<void> {
    let infos: ScoringInfos;
    try {
        infos = await getJson<ScoringInfos>(URLS.scoringInfos);
    } catch (error) {
        console.error("[preparation] refresh scoring infos failed:", error);
        return;
    }

    document.querySelectorAll<HTMLElement>("[data-prep-scoring-kind]").forEach((element) => {
        const texts = element.dataset["prepScoringKind"] === "question" ? infos.questions : infos.answers;
        element.textContent = texts[element.dataset["prepScoringId"] ?? ""] ?? "";
    });

    document.querySelectorAll<HTMLElement>("[data-prep-scoring-badge-kind]").forEach((element) => {
        const kind = element.dataset["prepScoringBadgeKind"] ?? "";
        const text = infos.badges[kind]?.[element.dataset["prepScoringBadgeId"] ?? ""] ?? "";
        element.textContent = text;
        element.style.display = text ? "" : "none";
    });
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

async function open(params: ScoringParams, spinner: Spinner = true): Promise<void> {
    if (!params.exam_pk) {
        renderError("Missing exam_pk.");
        new LocalModal(byId("modalScoringFormulas")).show();
        return;
    }

    try {
        setBody(await withSpinner(spinner, () => getText(withQuery(URLS.scoringFormulasModal, params))));
    } catch (error) {
        console.error("[preparation] open scoring formulas modal failed:", error);
        renderError("Unable to load formulas.");
    }
    new LocalModal(byId("modalScoringFormulas")).show();
}

// Saving rewrites the LaTeX files: the saving overlay shows it above the dialog, which stays open until the answer
async function submit(form: HTMLFormElement): Promise<void> {
    let response: ScoringResponse;
    try {
        // The form's own CSRF token is sent with its fields
        response = await withSpinner("saving", async () => (await postForm(form.action, {}, new FormData(form))).json() as Promise<ScoringResponse>);
    } catch (error) {
        console.error("[preparation] save scoring formulas failed:", error);

        const body = failureJson<ScoringResponse>(describeFailure(error));
        if (body.html) {
            setBody(body.html);
            return;
        }

        renderError(refusedReason(error) ?? "An error occurred while saving formulas.");
        return;
    }

    if (response.success) {
        new LocalModal(byId("modalScoringFormulas")).hide();

        if (response.scoring_update) {
            void followScoringUpdate(response.scoring_update.status_url);
        } else if (response.message) {
            showSaveToast(response.message, false);
        }
        return;
    }

    if (response.html) {
        setBody(response.html);
        return;
    }

    renderError(response.message || "Unable to save formulas.");
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
    void open({
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

    let response: ScoringResponse;
    try {
        response = await withSpinner("saving", () => postJson<ScoringResponse>(deleteUrl));
    } catch (error) {
        console.error("[preparation] delete scoring formula failed:", error);
        renderError(refusedReason(error) ?? "An error occurred while deleting formula.");
        return;
    }

    if (response.success) {
        reloadFromCurrentForm();
        if (response.scoring_update) void followScoringUpdate(response.scoring_update.status_url);
        return;
    }

    renderError(response.message || "Unable to delete formula.");
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
        void open(buildParams(button));
    });

    // Whatever the way the dialog is closed (saved, cancelled, formulas deleted inside it)
    document.addEventListener("hidden.bs.modal", (event) => {
        if ((event.target as Element).matches(Selectors.scoringModal)) void refreshScoringInfos();
    });

    document.addEventListener("submit", (event) => {
        const form = (event.target as Element).closest<HTMLFormElement>(Selectors.scoringForm);
        if (!form) return;

        event.preventDefault();
        void submit(form);
    });
}
