import { getPageBootstrap } from "@examc/helpers/page-bootstrap";

interface ConfirmDialogOptions {
    title: string;
    message: string;
    // Optional warning shown above the message
    warning?: string;
    confirmLabel?: string;
    cancelLabel?: string;
    // Bootstrap button class of the confirmation, e.g. "btn-danger" for a destructive action
    confirmClass?: string;
}

/**
 * Shows a Bootstrap confirmation dialog, built on the fly and removed once closed.
 * Resolves to true when the user confirms, false when the dialog is dismissed.
 */
export function confirmDialog({
    title,
    message,
    warning,
    confirmLabel = "Yes",
    cancelLabel = "No",
    confirmClass = "btn-primary",
}: ConfirmDialogOptions): Promise<boolean> {
    const element = document.createElement("div");
    element.className = "modal fade";
    element.tabIndex = -1;
    element.setAttribute("aria-hidden", "true");
    element.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"></h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div class="alert alert-warning mb-3" hidden></div>
            <p class="mb-0"></p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal"></button>
            <button type="button" class="btn btn-sm" data-confirm></button>
          </div>
        </div>
      </div>`;

    // Texts are set with textContent: they may contain user content
    element.querySelector(".modal-title")!.textContent = title;
    element.querySelector(".modal-body p")!.textContent = message;
    const alert = element.querySelector<HTMLElement>(".alert")!;
    if (warning) {
        alert.textContent = warning;
        alert.hidden = false;
    }
    element.querySelector("[data-bs-dismiss].btn-sm")!.textContent = cancelLabel;
    const confirmButton = element.querySelector<HTMLButtonElement>("[data-confirm]")!;
    confirmButton.textContent = confirmLabel;
    confirmButton.classList.add(confirmClass);

    // Opened over another dialog (e.g. the scoring formulas): shown above it, with its own backdrop
    const stacked = document.querySelector(".modal.show") !== null;

    document.body.append(element);
    const BootstrapModal = getPageBootstrap().Modal;
    const modal = new BootstrapModal(element);

    if (stacked) {
        element.style.zIndex = "1065";
        element.addEventListener("shown.bs.modal", () => {
            const backdrops = document.querySelectorAll<HTMLElement>(".modal-backdrop");
            const backdrop = backdrops[backdrops.length - 1];
            if (backdrop) backdrop.style.zIndex = "1060";
        }, { once: true });
    }

    return new Promise((resolve) => {
        let confirmed = false;

        confirmButton.addEventListener("click", () => {
            confirmed = true;
            modal.hide();
        });
        element.addEventListener("hidden.bs.modal", () => {
            modal.dispose();
            element.remove();
            // Bootstrap unlocks the page scroll on close, even when another dialog is still open
            if (document.querySelector(".modal.show")) document.body.classList.add("modal-open");
            resolve(confirmed);
        }, { once: true });

        modal.show();
    });
}
