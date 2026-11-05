/** What the server answered to an upload, whatever its status. */
export interface UploadResponse {
    status: number;
    ok: boolean;
    text: string;
}

export interface UploadOptions {
    /** Called as the body is sent, with the bytes sent so far and the total. */
    onProgress?: (loaded: number, total: number) => void;
    /** Aborts the upload: the promise then rejects with an AbortError. */
    signal?: AbortSignal;
}

/**
 * POSTs form data with XMLHttpRequest rather than fetch, which can't report upload progress.
 * Resolves once the server has answered, whatever its status; rejects if it can't be reached or on abort.
 *
 * @param {string} url - The URL to post to.
 * @param {FormData} body - What is sent, e.g. `new FormData(form)` (which holds its CSRF token).
 * @param {UploadOptions} options - Progress callback and abort signal.
 * @return {Promise<UploadResponse>} The response's status and text.
 */
export function postFormWithProgress(url: string, body: FormData, options: UploadOptions = {}): Promise<UploadResponse> {
    const { onProgress, signal } = options;

    return new Promise((resolve, reject) => {
        if (signal?.aborted) {
            reject(new DOMException('Upload aborted', 'AbortError'));
            return;
        }

        const xhr = new XMLHttpRequest();
        xhr.open('POST', url);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        if (onProgress) {
            xhr.upload.addEventListener('progress', event => {
                if (event.lengthComputable) onProgress(event.loaded, event.total);
            });
        }
        xhr.addEventListener('load', () => resolve({
            status: xhr.status,
            ok: xhr.status >= 200 && xhr.status < 300,
            text: xhr.responseText,
        }));
        xhr.addEventListener('error', () => reject(new Error('Network error')));
        xhr.addEventListener('abort', () => reject(new DOMException('Upload aborted', 'AbortError')));
        signal?.addEventListener('abort', () => xhr.abort(), { once: true });
        xhr.send(body);
    });
}

/**
 * A labelled progress bar: a percentage when it's known, an animated striped bar otherwise.
 * Works on markup already in the page (see `ProgressBar.create` for the expected structure), or builds its own.
 */
export class HttpProgressBar {
    private readonly label: HTMLElement;
    private readonly detail: HTMLElement;
    private readonly track: HTMLElement;
    private readonly bar: HTMLElement;

    /** @param element - The wrapper holding [data-progress-label], [data-progress-detail], .progress and .progress-bar. */
    public constructor(public readonly element: HTMLElement) {
        const label = element.querySelector<HTMLElement>('[data-progress-label]');
        const detail = element.querySelector<HTMLElement>('[data-progress-detail]');
        const track = element.querySelector<HTMLElement>('.progress');
        const bar = element.querySelector<HTMLElement>('.progress-bar');
        if (!label || !detail || !track || !bar) {
            throw new Error('A progress bar needs [data-progress-label], [data-progress-detail], .progress and .progress-bar elements.');
        }
        this.label = label;
        this.detail = detail;
        this.track = track;
        this.bar = bar;
    }

    /**
     * Builds a hidden progress bar, to be added to the page with `element`.
     *
     * @param ariaLabel - What the bar measures, for screen readers, e.g. "Upload progress".
     */
    public static create(ariaLabel: string): HttpProgressBar {
        const element = document.createElement('div');
        element.hidden = true;
        element.innerHTML = `
            <div class="d-flex justify-content-between small mb-1">
                <span data-progress-label aria-live="polite"></span>
                <span class="text-body-secondary" data-progress-detail></span>
            </div>
            <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100">
                <div class="progress-bar"></div>
            </div>`;
        // Set as an attribute rather than in the HTML string, so it's never parsed as markup.
        element.querySelector('.progress')!.setAttribute('aria-label', ariaLabel);
        return new HttpProgressBar(element);
    }

    /**
     * Shows the bar.
     *
     * @param label - What's happening, e.g. "Uploading the zip file…". Announced by screen readers when it changes.
     * @param percent - From 0 to 100, or undefined when it isn't known (an animated bar is shown instead).
     * @param detail - A short figure shown on the right, e.g. "12 of 40 pages".
     */
    public show(label: string, percent?: number, detail = ''): void {
        if (this.label.textContent !== label) this.label.textContent = label;
        this.detail.textContent = detail;

        const value = percent === undefined ? undefined : Math.round(Math.max(0, Math.min(100, percent)));
        this.bar.classList.toggle('progress-bar-striped', value === undefined);
        this.bar.classList.toggle('progress-bar-animated', value === undefined);
        this.bar.style.width = `${value ?? 100}%`;
        if (value === undefined) this.track.removeAttribute('aria-valuenow');
        else this.track.setAttribute('aria-valuenow', String(value));

        this.element.hidden = false;
    }

    public hide(): void {
        this.element.hidden = true;
    }
}