import { createAlert } from '@examc/helpers/alert';
import { byId } from '@examc/helpers/dom.ts';
import { HttpProgressBar, postFormWithProgress } from '@examc/helpers/http.ts';
import { showToast } from '@examc/helpers/toasts.ts';

const TOAST_TITLE = 'AMC project';

const megabytes = new Intl.NumberFormat(undefined, { style: 'unit', unit: 'megabyte', maximumFractionDigits: 1 });

/** What upload_amc_project answers once the project is imported. */
interface ImportResult {
    message: string;
    amc_url: string;
}

function parseJson(text: string): (Partial<ImportResult> & { error?: string }) | null {
    try {
        const value: unknown = JSON.parse(text);
        return value && typeof value === 'object' ? value as Partial<ImportResult> & { error?: string } : null;
    } catch {
        return null;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const form = byId<HTMLFormElement>('upload-amc-project-form');
    const result = byId('amc-project-upload-result');
    const button = form.querySelector<HTMLButtonElement>('button[type="submit"]');
    const buttonContent = button?.innerHTML ?? '';

    // Built here rather than in the template; shown under the form while the project is sent and imported.
    const progress = HttpProgressBar.create('AMC project upload progress');
    progress.element.classList.add('mt-3');
    form.after(progress.element);

    function setBusy(busyLabel: string | null): void {
        const busy = busyLabel !== null;
        form.setAttribute('aria-busy', String(busy));
        for (const element of form.elements) {
            if (element instanceof HTMLInputElement || element instanceof HTMLButtonElement) element.disabled = busy;
        }
        if (button) {
            button.innerHTML = busy
                ? `<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span> ${busyLabel}`
                : buttonContent;
        }
    }

    /** A success alert with a link to the AMC page. Built with the DOM: the message comes from the server. */
    function showSuccess({ message, amc_url }: ImportResult): void {
        const text = document.createElement('div');
        const link = document.createElement('a');
        link.className = 'alert-link';
        link.href = amc_url;
        link.textContent = 'Open the AMC page';
        text.append(`${message} `, link, '.');

        // Replaces the previous upload's message, if any.
        result.replaceChildren(createAlert({ alertType: 'success', content: text }));
        result.hidden = false;
    }

    form.addEventListener('submit', async event => {
        event.preventDefault();

        // Built before the inputs are disabled, as disabled inputs are left out.
        const body = new FormData(form);
        result.hidden = true;
        setBusy('Uploading…');
        progress.show('Uploading the zip file…', 0);

        try {
            const response = await postFormWithProgress(form.action, body, {
                onProgress: (loaded, total) => {
                    // Everything is sent: the server now imports the project, then answers.
                    if (loaded >= total) {
                        setBusy('Importing…');
                        progress.show('Importing the AMC project…');
                        return;
                    }
                    progress.show(
                        'Uploading the zip file…',
                        (loaded / total) * 100,
                        `${megabytes.format(loaded / 1e6)} of ${megabytes.format(total / 1e6)}`,
                    );
                },
            });
            const json = parseJson(response.text);

            if (!response.ok || !json?.message || !json.amc_url) {
                showToast(json?.error || `The AMC project couldn't be imported (error ${response.status}).`,
                    { error: true, title: TOAST_TITLE });
                return;
            }

            form.reset();
            showSuccess({ message: json.message, amc_url: json.amc_url });
        } catch {
            showToast('The AMC project couldn\'t be uploaded. Check your connection and try again.',
                { error: true, title: TOAST_TITLE });
        } finally {
            progress.hide();
            setBusy(null);
        }
    });
});