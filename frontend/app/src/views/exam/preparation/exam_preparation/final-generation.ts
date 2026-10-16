import { ConfirmModal } from "@examc/modals";

import { CFG, URLS } from "./config.ts";
import { ajaxGet, ajaxPost, showModal, WITHOUT_LOADING_MODAL } from "./ajax.ts";

// Final generation: a Celery task followed in the dialog and, when the dialog is closed or the page
// reloaded while it runs, in #final-generation-banner. The task goes on on the server in any case.

const DIALOG = "#generate_final_exam_files_dialog";

interface Summary {
    pages?: number;
    boxes?: number;
    marks?: number;
    zones?: number;
    digits?: number;
    unknown_payloads?: number;
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
    layout_result?: Summary;
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
    $("#generate_final_loading").hide();
    $("#generate_final_error").hide();
    $("#generate_final_success").hide().html("");
    $("#generate-final-checks").hide();
    $("#generate-final-anyway-button").hide();
}

// Problems of the exam content (see check_exam_content): the errors block, the warnings are confirmed with
// "Generate anyway"
function showGenFinalChecks(errors: string[] | undefined, warnings: string[] | undefined): void {
    const blocks: [string, string[] | undefined][] = [
        ["#generate-final-checks-errors", errors],
        ["#generate-final-checks-warnings", warnings],
    ];
    for (const [selector, items] of blocks) {
        const $list = $(selector + " ul").empty();
        // Texts set with .text(): they contain section and question titles
        (items ?? []).forEach((item) => $list.append($("<li>").text(item)));
        $(selector).toggle(Boolean(items && items.length));
    }
    $("#generate_final_loading").hide();
    $("#generate-final-checks").show();
    $("#generate-final-anyway-button").toggle(!(errors && errors.length));
}

function setGenFinalLoading(isLoading: boolean): void {
    if (isLoading) {
        $("#generate_final_loading").show();
    } else {
        $("#generate_final_loading").hide();
    }
}

function showGenFinalError(message?: string): void {
    $("#generate_final_error_message").val(message || "Error during final files generation.");
    $("#generate_final_error").show();
    $("#generate_final_loading").hide();
}

function escapeHtml(text: string): string {
    const element = document.createElement("div");
    element.textContent = text;
    return element.innerHTML;
}

function showGenFinalSuccess(data: FinalSuccess): void {
    const $success = $(`${DIALOG} #generate_final_success`);

    genFinalWasSuccessful = true;

    $("#generate_final_loading").hide();
    $("#generate_final_error").hide();

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
                <strong>Pages:</strong> ${summary.pages || 0}<br>
                <strong>Boxes:</strong> ${summary.boxes || 0}<br>
                <strong>Marks:</strong> ${summary.marks || 0}<br>
                <strong>Zones:</strong> ${summary.zones || 0}<br>
                <strong>Digits:</strong> ${summary.digits || 0}<br>
                <strong>Unknown payloads:</strong> ${summary.unknown_payloads || 0}
            </div>
            <div>
                The page is refreshed when you close this dialog: the final files can then be downloaded with the
                "Download final files" button.
            </div>
        `;

    $("#generate_final_success").html(resultHtml).show();
    $success.html(resultHtml).css("display", "block");
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
    if (!URLS.cancelFinal || !finalTracking) return;
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
    ajaxPost<ErrorResponse>(URLS.cancelFinal, {}, {
        ...WITHOUT_LOADING_MODAL,
        success: (data) => {
            // Still waiting for a worker: nothing runs, so no task will report its end
            if (data.status === "cancelled") finishFinalGeneration(false, "The generation was cancelled.");
        },
        error: (xhr) => {
            const data = (xhr.responseJSON ?? {}) as ErrorResponse;
            // 404: it ended in the meantime, its end is shown by the tracking
            if (xhr.status !== 404) showGenFinalError(data.error || "Impossible to cancel the generation.");
            showCancelFinalButtons(true);
        },
    });
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
        if (!dialogOpen) showModal(DIALOG);
        showGenFinalError(typeof payload === "string" ? payload : "Generation failed.");
    }
}

function trackFinalGeneration(taskId: string, startedAt?: number | null): void {
    if (finalTracking && finalTracking.taskId === taskId) return;
    if (typeof CeleryProgressBar === "undefined" || !URLS.celeryTaskStatusTemplate) {
        showGenFinalError("The progress of the generation cannot be followed (Celery progress bar missing).");
        return;
    }

    finalTracking = { taskId, startedAt: startedAt || Date.now() };
    if (finalElapsedTimer !== null) window.clearInterval(finalElapsedTimer);
    finalElapsedTimer = window.setInterval(updateFinalElapsed, 1000);
    updateFinalElapsed();
    showFinalBanner(!isGenFinalDialogOpen());
    showCancelFinalButtons(true);

    CeleryProgressBar.initProgressBar(URLS.celeryTaskStatusTemplate.replace("__TASK_ID__", taskId), {
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

export function generateFinalExamFiles(confirmWarnings = false): void {
    if (!URLS.generateFinalStart) {
        console.warn("[preparation] Missing generateFinalStart URL");
        return;
    }

    genFinalWasSuccessful = false;
    resetGenFinalUi();
    setGenFinalLoading(true);
    setFinalProgress(0, "Starting...");
    showModal(DIALOG);

    // Already running (this page loaded before, or another user): follow it
    if (finalTracking) return;

    ajaxGet<StartResponse>(URLS.generateFinalStart, confirmWarnings ? { confirm_warnings: 1 } : {}, {
        ...WITHOUT_LOADING_MODAL,
        success: (data) => {
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
        },

        error: (xhr) => {
            const data = (xhr.responseJSON ?? {}) as ErrorResponse;
            // 409: a generation of this exam is already running, followed instead of starting another one
            if (xhr.status === 409 && data.task_id) {
                setFinalProgress(0, data.error || "A final generation is already running.");
                trackFinalGeneration(data.task_id);
                return;
            }
            if (data.errors && data.errors.length) {
                showGenFinalChecks(data.errors, data.warnings);
                return;
            }
            showGenFinalError(data.error || xhr.responseText || "Error starting final exam files generation.");
        },
    });
}

function normalizeGenFinalSuccessPayload(result: RawFinalResult | undefined): FinalSuccess {
    if (!result) return { warnings: [], summary: {} };

    const payload = result.result ?? result;
    const layout = payload.layout_result;

    return {
        ...(payload.build_id !== undefined ? { build_id: payload.build_id } : {}),
        warnings: payload.warnings ?? [],
        summary: payload.summary ?? (layout ? {
            pages: layout.pages || 0,
            boxes: layout.boxes || 0,
            marks: layout.marks || 0,
            zones: layout.zones || 0,
            digits: layout.digits || 0,
            unknown_payloads: layout.unknown_payloads || 0,
        } : {}),
    };
}

// The page changes once the exam is finalized (download button, "locked" banner, read-only editing):
// reloaded when the dialog of a successful final generation is closed, whatever the way (Close, ×, Escape,
// backdrop). The Bootstrap 5 "hidden" event does not always reach a document listener on this page
// (Bootstrap 4 is loaded too): listened on the dialog itself, natively and with jQuery, and the Close
// button reloads directly.
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
        showModal(DIALOG);
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
