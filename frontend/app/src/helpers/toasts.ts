import { Toast } from "bootstrap";

export interface ToastOptions {
    /** Shown as an error: red icon, announced right away by screen readers, and visible longer. */
    error?: boolean;
    /** The header's title. Defaults to "Done" or "Error". */
    title?: string;
    /** How long the toast stays, in milliseconds. Defaults to 4 seconds, 8 for an error. */
    delay?: number;
    /** Whether the toast hides by itself after `delay`. Defaults to true; false keeps it until it's closed. */
    autohide?: boolean;
}

/** How often the time shown in a toast is updated. */
const TIME_UPDATE_INTERVAL = 30_000;

const relativeTime = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

/** The fixed corner where toasts stack, created on the first toast. */
function toastContainer(): HTMLElement {
    let container = document.getElementById("examc-toasts");
    if (!container) {
        container = document.createElement("div");
        container.id = "examc-toasts";
        container.className = "toast-container position-fixed top-0 end-0 p-3";
        document.body.append(container);
    }
    return container;
}

/** How long ago a moment was, for people: "just now", "1 minute ago", "2 hours ago"… */
function timeAgo(since: Date): string {
    const minutes = Math.floor((Date.now() - since.getTime()) / 60_000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return relativeTime.format(-minutes, "minute");
    return relativeTime.format(-Math.floor(minutes / 60), "hour");
}

/**
 * Shows a short message in the top right corner. It hides by itself unless `autohide` is false.
 *
 * @param {string} message - The message, as text.
 * @param {ToastOptions} options - Whether it's an error, its title, and how long it stays.
 */
export function showToast(message: string, { error = false, title, delay, autohide = true }: ToastOptions = {}): void {
    const shownAt = new Date();

    const element = document.createElement("div");
    element.className = "toast";
    element.role = error ? "alert" : "status";
    element.ariaLive = error ? "assertive" : "polite";
    element.ariaAtomic = "true";
    element.innerHTML = `
        <div class="toast-header">
            <i class="fa-solid ${error ? "fa-circle-exclamation text-danger" : "fa-circle-check text-success"} me-2"
               aria-hidden="true"></i>
            <strong class="me-auto" data-toast-title></strong>
            <small class="text-body-secondary"><time data-toast-time></time></small>
            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body" data-toast-message></div>`;

    // Set as text: a message can include what the user or the server wrote
    element.querySelector<HTMLElement>("[data-toast-title]")!.textContent = title ?? (error ? "Error" : "Done");
    element.querySelector<HTMLElement>("[data-toast-message]")!.textContent = message;

    // The time it appeared: relative, kept up to date while shown, and exact on hover
    const time = element.querySelector<HTMLTimeElement>("[data-toast-time]")!;
    time.dateTime = shownAt.toISOString();
    time.title = shownAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const updateTime = (): void => { time.textContent = timeAgo(shownAt); };
    updateTime();
    const timer = window.setInterval(updateTime, TIME_UPDATE_INTERVAL);

    element.addEventListener("hidden.bs.toast", () => {
        window.clearInterval(timer);
        element.remove();
    });

    toastContainer().prepend(element);
    new Toast(element, { autohide, delay: delay ?? (error ? 8000 : 4000) }).show();
}