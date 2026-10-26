import { describeFailure, failureJson, getJson, postJson } from "@examc/helpers/http.ts";

import { previewStatusUrl, URLS } from "./config.ts";
import { getElement, hideElement, showElement, toggleElement } from "./ajax.ts";
import { LocalModal } from "@examc/modals/local.ts";
import { byId } from "@examc/helpers/dom.ts";

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
    hideElement("#exam_preview_loading");
    hideElement("#exam_preview_error");
    hideElement("#exam_preview_pdf");
    getElement<HTMLIFrameElement>("#exam_preview_pdf")?.setAttribute("src", "");
}

function setPreviewLoading(isLoading: boolean): void {
    toggleElement("#exam_preview_loading", isLoading);
}

function showPreviewError(message?: string): void {
    const field = getElement<HTMLTextAreaElement>("#exam_preview_error_message");
    if (field) field.value = message || "Error during preview generation.";
    showElement("#exam_preview_error");
    hideElement("#exam_preview_pdf");
    hideElement("#exam_preview_loading");
}

function showPreviewPdf(pdfUrl: string): void {
    getElement<HTMLIFrameElement>("#exam_preview_pdf")?.setAttribute("src", pdfUrl);
    showElement("#exam_preview_pdf");
    hideElement("#exam_preview_error");
    hideElement("#exam_preview_loading");
}

export function stopPreviewPolling(): void {
    if (previewPollingTimer) {
        clearTimeout(previewPollingTimer);
        previewPollingTimer = null;
    }
}

export async function previewExam(): Promise<void> {
    stopPreviewPolling();
    resetPreviewUi();
    setPreviewLoading(true);
    new LocalModal(byId("exam_preview_dialog")).show();

    let data: PreviewStartResponse;
    try {
        data = await postJson<PreviewStartResponse>(URLS.previewStart);
    } catch (error) {
        const failure = describeFailure(error);
        showPreviewError(failureJson<PreviewStartResponse>(failure).error || failure.text || "Error starting preview.");
        return;
    }

    if (!data.job_id) {
        showPreviewError("Impossible to start preview.");
        return;
    }

    await pollPreviewStatus(data.job_id);
}

async function pollPreviewStatus(jobId: string, attempt = 0): Promise<void> {
    const maxAttempts = 60;
    const url = previewStatusUrl(jobId);

    if (attempt >= maxAttempts) {
        showPreviewError("Le preview prend trop de temps ou le worker est bloqué.");
        return;
    }

    let data: PreviewStatusResponse;
    try {
        data = await getJson<PreviewStatusResponse>(url);
    } catch {
        showPreviewError("Erreur lors de la récupération du statut.");
        return;
    }

    if (data.status === "pending" || data.status === "running") {
        setPreviewLoading(true);
        previewPollingTimer = window.setTimeout(() => {
            void pollPreviewStatus(jobId, attempt + 1);
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
}
