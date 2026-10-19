// Saving rewrites the LaTeX files of the exam, which can take a few seconds: the overlay of the template
// (#prep-saving-overlay) is shown while a saving request (htmx, or a reorder) is running, but only if it lasts
// more than 400 ms (no flash on fast ones).

const SHOW_DELAY_MS = 400;

let pending = 0;
let timer: number | null = null;

function start(): void {
    pending++;
    if (timer === null) {
        timer = window.setTimeout(() => {
            const overlay = document.getElementById("prep-saving-overlay");
            if (overlay) overlay.style.display = "block";
        }, SHOW_DELAY_MS);
    }
}

function end(): void {
    if (pending === 0) return;
    if (--pending > 0) return;
    if (timer !== null) clearTimeout(timer);
    timer = null;
    const overlay = document.getElementById("prep-saving-overlay");
    if (overlay) overlay.style.display = "none";
}

/** Runs a saving task behind the overlay. */
export async function withSavingOverlay<T>(task: () => Promise<T>): Promise<T> {
    start();
    try {
        return await task();
    } finally {
        end();
    }
}

const isSaving = (event: CustomEvent<{ requestConfig: { verb: string } }>): boolean => (event.detail.requestConfig.verb || "get") !== "get";

export function initSavingOverlay(): void {
    document.body.addEventListener("htmx:beforeRequest", (event) => {
        if (isSaving(event)) start();
    });
    document.body.addEventListener("htmx:afterRequest", (event) => {
        if (isSaving(event)) end();
    });
}
