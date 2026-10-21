import { describeFailure, failureJson, postJson } from "@examc/helpers/http.ts";
import { ConfirmModal, LocalModal } from "@examc/modals";

import { celeryTaskStatusUrl, CFG, URLS } from "./config.ts";
import { getElement, hideElement, showElement, toggleElement } from "./ajax.ts";
import { byId } from "@examc/helpers/dom.ts";

// Final generation: a Celery task followed in the dialog and, when the dialog is closed or the page
// reloaded while it runs, in #final-generation-banner. The task goes on on the server in any case.

const DIALOG = "#generate_final_exam_files_dialog";
const SUCCESS = `${DIALOG} #generate_final_success`;

interface Summary {
    copies?: number;
    pages_per_copy?: number;
    pages?: number;
}

/** Result of the generation task (possibly wrapped in `result`). */
interface RawFinalResult extends Summary {
    result?: RawFinalResult;
    build_id?: string;
    pdf_path?: string;
    subject_pdf_path?: string;
    catalog_pdf_path?: string;
    exam_calage_xy_path?: string;
    warnings?: string[];
    summary?: Summary;
}

interface FinalSuccess {
    build_id?: string;
    warnings: string[];
    summary: Summary;
}

interface StartResponse {
    job_id?: string;
    task_id?: string;
    warnings?: string[];
}

interface ErrorResponse {
    error?: string;
    errors?: string[];
    warnings?: string[];
    task_id?: string;
    status?: string;
}

let genFinalWasSuccessful = false;
let finalTracking: { taskId: string; startedAt: number } | null = null;
let finalElapsedTimer: number | null = null;
let reloadWhenFinalDialogClosed = false;

function resetGenFinalUi(): void {
    hideElement("#generate_final_loading");
    hideElement("#generate_final_error");
    hideElement(SUCCESS);
    const success = getElement(SUCCESS);
    if (success) success.innerHTML = "";
    hideElement("#generate-final-checks");
    hideElement("#generate-final-anyway-button");
}

// Problems of the exam content (see check_exam_content): the errors block, the warnings are confirmed with
// "Generate anyway"
function showGenFinalChecks(errors: string[] | undefined, warnings: string[] | undefined): void {
    const blocks: [string, string[] | undefined][] = [
        ["#generate-final-checks-errors", errors],
        ["#generate-final-checks-warnings", warnings],
    ];
    for (const [selector, items] of blocks) {
        const list = getElement(selector + " ul");
        list?.replaceChildren(...(items ?? []).map((item) => {
            // Texts set with textContent: they contain section and question titles
            const li = document.createElement("li");
            li.textContent = item;
            return li;
        }));
        toggleElement(selector, Boolean(items && items.length));
    }
    hideElement("#generate_final_loading");
    showElement("#generate-final-checks");
    toggleElement("#generate-final-anyway-button", !(errors && errors.length));
}

function setGenFinalLoading(isLoading: boolean): void {
    toggleElement("#generate_final_loading", isLoading);
}

function showGenFinalError(message?: string): void {
    const field = getElement<HTMLTextAreaElement>("#generate_final_error_message");
    if (field) field.value = message || "Error during final files generation.";
    showElement("#generate_final_error");
    hideElement("#generate_final_loading");
}

function escapeHtml(text: string): string {
    const element = document.createElement("div");
    element.textContent = text;
    return element.innerHTML;
}

function showGenFinalSuccess(data: FinalSuccess): void {
    genFinalWasSuccessful = true;

    hideElement("#generate_final_loading");
    hideElement("#generate_final_error");

    const summary = data.summary;
    let warningsHtml = "";

    if (data.warnings.length > 0) {
        warningsHtml = data.warnings
            .map((w) => `<div class="alert alert-warning">${escapeHtml(w)}</div>`)
            .join("");
    }

    const resultHtml = `
            <div class="alert alert-success">Final exam generated successfully.</div>
            ${warningsHtml}
            <div class="mb-3">
                <strong>Build ID:</strong> ${escapeHtml(data.build_id || "-")}<br>
                <strong>Copies:</strong> ${summary.copies || 0}<br>
                <strong>Pages per copy:</strong> ${summary.pages_per_copy || 0}<br>
                <strong>Pages:</strong> ${summary.pages || 0}
            </div>
            <div>
                The page is refreshed when you close this dialog: the final files can then be downloaded with the
                "Download final files" button.
            </div>
        `;

    const success = getElement(SUCCESS);
    if (success) {
        success.innerHTML = resultHtml;
        success.style.display = "block";
    }
}

function setFinalProgress(percent: number | null, message?: string): void {
    const value = Math.max(0, Math.min(100, Math.round(percent ?? 0)));
    for (const id of ["generate-final-progress-bar", "final-generation-banner-bar"]) {
        const bar = document.getElementById(id);
        if (!bar || percent === null) continue;
        bar.style.width = value + "%";
        bar.textContent = value + "%";
    }
    for (const id of ["generate-final-progress-message", "final-generation-banner-message"]) {
        const element = document.getElementById(id);
        if (element && message) element.textContent = message;
    }
}

function showFinalBanner(show: boolean): void {
    const banner = document.getElementById("final-generation-banner");
    if (banner) banner.hidden = !show;
    const button = document.getElementById("generate-final-button") as HTMLButtonElement | null;
    if (button) button.disabled = !!finalTracking;
}

function isGenFinalDialogOpen(): boolean {
    const dialog = document.getElementById("generate_final_exam_files_dialog");
    return !!dialog && dialog.classList.contains("show");
}

function updateFinalElapsed(): void {
    const element = document.getElementById("generate-final-elapsed");
    if (!element || !finalTracking) return;
    const seconds = Math.max(0, Math.round((Date.now() - finalTracking.startedAt) / 1000));
    element.textContent = Math.floor(seconds / 60) + " min " + String(seconds % 60).padStart(2, "0") + " s";
}

function showCancelFinalButtons(show: boolean): void {
    for (const id of ["generate-final-cancel-button", "final-generation-banner-cancel"]) {
        const button = document.getElementById(id) as HTMLButtonElement | null;
        if (!button) continue;
        button.disabled = false;
        if (id === "generate-final-cancel-button") button.style.display = show ? "" : "none";
    }
}

// Stops the running generation (it stops within a few seconds, the exam is then editable again)
async function cancelFinalGeneration(): Promise<void> {
    if (!finalTracking) return;
    const confirmed = await ConfirmModal.confirm({
        title: "Cancel the final generation",
        message: "Cancel the final generation? Nothing will be generated.",
        confirmLabel: "Yes, cancel it",
        confirmClass: "btn-danger",
    });
    // The generation may have ended while the question was open
    if (!confirmed || !finalTracking) return;

    for (const id of ["generate-final-cancel-button", "final-generation-banner-cancel"]) {
        const button = document.getElementById(id) as HTMLButtonElement | null;
        if (button) button.disabled = true;
    }
    setFinalProgress(null, "Cancelling...");
    try {
        const data = await postJson<ErrorResponse>(URLS.cancelFinal);
        // Still waiting for a worker: nothing runs, so no task will report its end
        if (data.status === "cancelled") finishFinalGeneration(false, "The generation was cancelled.");
    } catch (error) {
        const failure = describeFailure(error);
        // 404: it ended in the meantime, its end is shown by the tracking
        if (failure.status !== 404) showGenFinalError(failureJson<ErrorResponse>(failure).error || "Impossible to cancel the generation.");
        showCancelFinalButtons(true);
    }
}

function stopFinalTracking(): void {
    showCancelFinalButtons(false);
    finalTracking = null;
    if (finalElapsedTimer !== null) window.clearInterval(finalElapsedTimer);
    finalElapsedTimer = null;
    showFinalBanner(false);
}

// Shows the end of the generation: in the dialog when it is open, else the page is reloaded (success) or the
// dialog is opened with the error
function finishFinalGeneration(ok: boolean, payload?: unknown): void {
    const dialogOpen = isGenFinalDialogOpen();
    stopFinalTracking();
    if (ok) {
        if (!dialogOpen) {
            window.location.reload();
            return;
        }
        showGenFinalSuccess(normalizeGenFinalSuccessPayload(payload as RawFinalResult | undefined));
    } else {
        // The exam was locked by the generation (see isLocked): the page is reloaded when the dialog is closed
        if (CFG.isLocked && !CFG.isFinalized) reloadWhenFinalDialogClosed = true;
        if (!dialogOpen) new LocalModal(byId(DIALOG)).show();
        showGenFinalError(typeof payload === "string" ? payload : "Generation failed.");
    }
}

function trackFinalGeneration(taskId: string, startedAt?: number | null): void {
    if (finalTracking && finalTracking.taskId === taskId) return;
    if (typeof CeleryProgressBar === "undefined") {
        showGenFinalError("The progress of the generation cannot be followed (Celery progress bar missing).");
        return;
    }

    finalTracking = { taskId, startedAt: startedAt || Date.now() };
    if (finalElapsedTimer !== null) window.clearInterval(finalElapsedTimer);
    finalElapsedTimer = window.setInterval(updateFinalElapsed, 1000);
    updateFinalElapsed();
    showFinalBanner(!isGenFinalDialogOpen());
    showCancelFinalButtons(true);

    CeleryProgressBar.initProgressBar(celeryTaskStatusUrl(taskId), {
        progressBarId: "generate-final-progress-bar",
        progressBarMessageId: "generate-final-progress-message",
        pollInterval: 2000,
        onProgress: (_bar, _message, progress) => {
            setFinalProgress(progress.percent, progress.description || "Processing...");
        },
        onSuccess: () => {
            setFinalProgress(100, "Done.");
        },
        onResult: (_resultElement, result) => {
            finishFinalGeneration(true, result);
        },
        onTaskError: (_bar, _message, excMessage) => {
            finishFinalGeneration(false, excMessage);
        },
        onError: (_bar, _message, excMessage) => {
            finishFinalGeneration(false, "Error while following the generation: " + (excMessage || "unknown error"));
        },
    });
}

export async function generateFinalExamFiles(confirmWarnings = false): Promise<void> {
    genFinalWasSuccessful = false;
    resetGenFinalUi();
    setGenFinalLoading(true);
    setFinalProgress(0, "Starting...");
    new LocalModal(byId(DIALOG)).show();

    // Already running (this page loaded before, or another user): follow it
    if (finalTracking) return;

    let data: StartResponse;
    try {
        data = await postJson<StartResponse>(URLS.generateFinalStart, confirmWarnings ? { confirm_warnings: 1 } : {});
    } catch (error) {
        const failure = describeFailure(error);
        const body = failureJson<ErrorResponse>(failure);
        // 409: a generation of this exam is already running, followed instead of starting another one
        if (failure.status === 409 && body.task_id) {
            setFinalProgress(0, body.error || "A final generation is already running.");
            trackFinalGeneration(body.task_id);
            return;
        }
        if (body.errors && body.errors.length) {
            showGenFinalChecks(body.errors, body.warnings);
            return;
        }
        showGenFinalError(body.error || failure.text || "Error starting final exam files generation.");
        return;
    }

    // Not started: warnings to confirm
    if (data.warnings && data.warnings.length && !data.job_id) {
        showGenFinalChecks([], data.warnings);
        return;
    }
    if (!data.job_id || !data.task_id) {
        showGenFinalError("Impossible to start final exam files generation.");
        return;
    }
    trackFinalGeneration(data.task_id);
}

function normalizeGenFinalSuccessPayload(result: RawFinalResult | undefined): FinalSuccess {
    if (!result) return { warnings: [], summary: {} };

    const payload = result.result ?? result;

    return {
        ...(payload.build_id !== undefined ? { build_id: payload.build_id } : {}),
        warnings: payload.warnings ?? [],
        summary: payload.summary ?? {},
    };
}

// The page changes once the exam is finalized (download button, "locked" banner, read-only editing):
// reloaded when the dialog of a successful final generation is closed, whatever the way (Close, ×, Escape,
// backdrop). The Bootstrap 5 "hidden" event does not always reach a document listener on this page
// (Bootstrap 4 is loaded too): listened on the dialog itself, and the Close button reloads directly.
function reloadAfterFinalGeneration(): void {
    if (genFinalWasSuccessful) {
        genFinalWasSuccessful = false;
        window.location.reload();
    } else if (reloadWhenFinalDialogClosed) {
        window.location.reload();
    } else if (finalTracking) {
        // Closed while running: the page is reloaded to lock the exam (the generation is then followed in the
        // banner, see activeFinalTaskId), or followed in the banner when it is already locked
        if (!CFG.isLocked) {
            window.location.reload();
        } else {
            showFinalBanner(true);
        }
    }
}

export function initFinalGeneration(): void {
    // A generation running when the page was loaded (closed dialog, other user...)
    if (CFG.activeFinalTaskId) {
        const startedAt = Date.parse(CFG.activeFinalStartedAt);
        trackFinalGeneration(CFG.activeFinalTaskId, Number.isNaN(startedAt) ? null : startedAt);
    }
    document.getElementById("final-generation-banner-cancel")?.addEventListener("click", () => void cancelFinalGeneration());
    document.getElementById("generate-final-cancel-button")?.addEventListener("click", () => void cancelFinalGeneration());
    document.getElementById("final-generation-banner-show")?.addEventListener("click", () => {
        resetGenFinalUi();
        setGenFinalLoading(true);
        showFinalBanner(false);
        new LocalModal(byId(DIALOG)).show();
    });

    const genFinalDialog = document.getElementById("generate_final_exam_files_dialog");
    if (genFinalDialog) {
        genFinalDialog.addEventListener("hidden.bs.modal", reloadAfterFinalGeneration);
        genFinalDialog.querySelectorAll("[data-bs-dismiss='modal']").forEach((button) => {
            button.addEventListener("click", () => {
                if (genFinalWasSuccessful) reloadAfterFinalGeneration();
            });
        });
    }
}
