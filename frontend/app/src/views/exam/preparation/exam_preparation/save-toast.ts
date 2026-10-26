// Feedback of the saves of the page: a toast in the corner

let saveToastTimer: number | null = null;

export function showSaveToast(message: string, isError: boolean): void {
    let toast = document.getElementById("prep-save-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "prep-save-toast";
        toast.setAttribute("role", "status");
        toast.setAttribute("aria-live", "polite");
        document.body.appendChild(toast);
    }

    toast.textContent = message;
    toast.classList.toggle("is-error", isError);
    toast.classList.add("is-visible");

    if (saveToastTimer !== null) clearTimeout(saveToastTimer);
    saveToastTimer = window.setTimeout(() => {
        toast.classList.remove("is-visible");
    }, isError ? 6000 : 2500);
}
