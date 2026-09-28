import { Collapse } from 'bootstrap';
import { getModal } from '@examc/helpers/modals.ts';

declare global {
    interface Window {
        onUploadScansComplete?: () => void;
        call_amc_automatic_datacapture_process?: () => void;
        SidebarCollapse?: () => void;
    }
}

const progressModalElement = document.getElementById('celeryProgressBarModal');

/**
 * Updates the progress bar element and its message from the task's progress data.
 */
export function processProgress(
    progressBarElement: HTMLElement,
    progressBarMessageElement: HTMLElement,
    progress: { percent: number; description?: string },
): void {
    progressBarElement.style.width = `${progress.percent}%`;
    progressBarElement.textContent = `${progress.percent}%`;
    progressBarMessageElement.textContent = progress.description || 'Processing...';
}

function showDownloadLink(fileName: string): void {
    const examPk = progressModalElement?.dataset.examPk;
    const message = document.getElementById('progress-bar-message');
    if (!examPk || !message) return;

    const link = document.createElement('a');
    link.href = `/download_marked_files/${encodeURIComponent(fileName)}/${encodeURIComponent(examPk)}`;
    link.download = fileName;
    link.textContent = 'Click to download marked files';

    message.replaceChildren('Success!', document.createElement('br'), link);
}

function processResult(_resultElement: HTMLElement | null, result: unknown): void {
    if (typeof result !== 'string') return;
    const progressModal = getModal({ type: 'local', element: progressModalElement });

    if (result.includes('Process finished')) {
        setTimeout(() => progressModal.hide(), 1000);
    } else if (result.startsWith('marked_') && result.endsWith('.zip')) {
        showDownloadLink(result);
    } else if (result === 'upload_scans_ok') {
        progressModal.hide();
        if (window.onUploadScansComplete) {
            window.onUploadScansComplete();
        } else {
            window.call_amc_automatic_datacapture_process?.();
        }
    }
}

const progressUrl = progressModalElement?.dataset.progressUrl;
if (progressModalElement && progressUrl) {
    getModal({ type: 'local', element: progressModalElement }).show();

    CeleryProgressBar.initProgressBar(progressUrl, {
        onProgress: processProgress,
        onResult: processResult,
    });
}

let ajaxInfoModalInitialized = false;

export function setAjaxInfoModalLocked(locked: boolean): void {
    const okBtn = document.querySelector<HTMLButtonElement>('#ajax_modal_ok');
    const closeBtn = document.querySelector<HTMLButtonElement>('#ajax_modal_close');
    if (!okBtn || !closeBtn) return;

    okBtn.disabled = locked;
    closeBtn.disabled = locked;

    // Visually disable the "X" (top-right)
    const xBtn = document.querySelector<HTMLButtonElement>('#ajax_info_modal .close, #ajax_info_modal .btn-close');
    if (xBtn) {
        xBtn.style.pointerEvents = locked ? 'none' : 'auto';
        xBtn.style.opacity = locked ? '0.5' : '1';
    }

    // Configure the modal once (prevents closing via backdrop/ESC)
    if (!ajaxInfoModalInitialized) {
        getModal({
            type: 'local',
            element: document.getElementById('ajax_info_modal'),
            modalOptions: { backdrop: 'static', keyboard: false },
        }).show();
        ajaxInfoModalInitialized = true;
    }
}

// Hide submenus
document.querySelectorAll<HTMLElement>('#body-row .collapse').forEach((element) => {
    Collapse.getOrCreateInstance(element, { toggle: false }).hide();
});

// Collapse/Expand icon
document.getElementById('collapse-icon')?.classList.add('fa-angle-double-left');

// Collapse click
document.querySelectorAll<HTMLElement>('[data-toggle=sidebar-colapse]').forEach((element) => {
    element.addEventListener('click', () => window.SidebarCollapse?.());
});