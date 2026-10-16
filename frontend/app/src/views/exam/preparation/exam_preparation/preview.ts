import { URLS } from "./config.ts";
import { ajaxGet, showModal, WITHOUT_LOADING_MODAL } from "./ajax.ts";

interface PreviewStartResponse {
    job_id?: string;
    error?: string;
}

interface PreviewStatusResponse {
    status?: string;
    error?: string;
    pdf_url?: string;
}

let previewPollingTimer: number | null = null;

function resetPreviewUi(): void {
    $("#exam_preview_loading").hide();
    $("#exam_preview_error").hide();
    $("#exam_preview_pdf").hide().attr("src", "");
}

function setPreviewLoading(isLoading: boolean): void {
    if (isLoading) {
        $("#exam_preview_loading").show();
    } else {
        $("#exam_preview_loading").hide();
    }
}

function showPreviewError(message?: string): void {
    $("#exam_preview_error_message").val(message || "Error during preview generation.");
    $("#exam_preview_error").show();
    $("#exam_preview_pdf").hide();
    $("#exam_preview_loading").hide();
}

function showPreviewPdf(pdfUrl: string): void {
    $("#exam_preview_pdf").attr("src", pdfUrl).show();
    $("#exam_preview_error").hide();
    $("#exam_preview_loading").hide();
}

export function stopPreviewPolling(): void {
    if (previewPollingTimer) {
        clearTimeout(previewPollingTimer);
        previewPollingTimer = null;
    }
}

export function previewExam(): void {
    if (!URLS.previewStart) {
        console.warn("[preparation] Missing previewStart URL");
        return;
    }

    stopPreviewPolling();
    resetPreviewUi();
    setPreviewLoading(true);
    showModal("#exam_preview_dialog");

    ajaxGet<PreviewStartResponse>(URLS.previewStart, {}, {
        ...WITHOUT_LOADING_MODAL,
        success: (data) => {
            if (!data.job_id) {
                showPreviewError("Impossible to start preview.");
                return;
            }

            pollPreviewStatus(data.job_id);
        },
        error: (xhr) => {
            let message = "Error starting preview.";
            const data = xhr.responseJSON as PreviewStartResponse | undefined;
            if (data && data.error) {
                message = data.error;
            } else if (xhr.responseText) {
                message = xhr.responseText;
            }
            showPreviewError(message);
        },
    });
}

function pollPreviewStatus(jobId: string, attempt = 0): void {
    const maxAttempts = 60;
    const url = URLS.previewStatus.replace("__JOB_ID__", jobId);

    if (attempt >= maxAttempts) {
        showPreviewError("Le preview prend trop de temps ou le worker est bloqué.");
        return;
    }

    ajaxGet<PreviewStatusResponse>(url, {}, {
        ...WITHOUT_LOADING_MODAL,
        success: (data) => {
            if (data.status === "pending" || data.status === "running") {
                setPreviewLoading(true);
                previewPollingTimer = window.setTimeout(() => {
                    pollPreviewStatus(jobId, attempt + 1);
                }, 1000);
                return;
            }

            if (data.status === "error") {
                showPreviewError(data.error || "Erreur de compilation.");
                return;
            }

            if (data.status === "success" && data.pdf_url) {
                showPreviewPdf(data.pdf_url);
                return;
            }

            showPreviewError("Statut de preview inattendu.");
        },
        error: () => {
            showPreviewError("Erreur lors de la récupération du statut.");
        },
    });
}
