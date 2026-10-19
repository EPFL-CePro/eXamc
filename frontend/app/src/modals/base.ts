import type { ExamcModalOptions } from "@examc/types/modals";
import { Modal } from "bootstrap";

/** The parts of a modal built on the fly. */
interface GeneratedModalParts {
    /** Additional classes for the .modal-dialog element, e.g. "modal-lg". */
    extraDialogClass?: string;

    /** Don't show .modal-header */
    noHeader?: boolean;
    /** Don't show .modal-footer */
    noFooter?: boolean;

    /** Overrides the max-width set by boostrap*/
    maxWidth?: string;

    /** HTML of the .modal-title element */
    titleContent?: string;
    /** HTML of the .modal-body element. */
    bodyContent?: string;
    /** HTML inside the .modal-footer element. */
    footerContent?: string;
}

/** A Bootstrap modal, with the behavior shared by every kind of eXamc modal. */
export abstract class ExamcModal {
    protected readonly element: HTMLElement;
    protected readonly modal: Modal;
    private readonly titleEl: HTMLElement | null;

    protected constructor(element: HTMLElement, modalOptions?: ExamcModalOptions) {
        this.element = element;
        this.titleEl = element.querySelector<HTMLElement>(".modal-title");
        this.modal = Modal.getOrCreateInstance(element, modalOptions);
    }

    public show(): void {
        this.modal.show();
    }

    public hide(): void {
        this.modal.hide();
    }

    public setTitle(title: string): void {
        if (this.titleEl) {
            this.titleEl.textContent = title;
        } else {
            console.error("Couldn't set the content of undefined title HTML element for the following modal :", this);
        }
    }

    /**
     * Builds a modal on the fly: added to the page, and removed once closed.
     * Opened over another dialog, it's shown above it, with its own backdrop.
     *
     * @param {GeneratedModalParts} parts - The modal's dialog class, body and footer.
     * @returns {HTMLElement} The modal element.
     */
    protected static createElement(options?: GeneratedModalParts): HTMLElement {
        const { 
            extraDialogClass = "modal-dialog modal-dialog-centered",
            maxWidth,
            noHeader = false, noFooter = false,
            titleContent = "", bodyContent = "", footerContent = ""
        } = options || {};

        const modalEl = document.createElement("div");
        modalEl.className = "modal fade";
        modalEl.tabIndex = -1;
        modalEl.role = "dialog";
        modalEl.setAttribute("aria-hidden", "true");

        // build header
        let header = `
            <div class="modal-header">
                <h5 class="modal-title">${titleContent}</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
        `;
        if (noHeader) header = "";

        // build footer
        let footer = `<div class="modal-footer">${footerContent}</div>`;
        if (noFooter) footer = "";

        let modalDialogStyle = "";
        if (maxWidth) modalDialogStyle = `style="max-width:${maxWidth}"`;

        modalEl.innerHTML = `
            <div class="modal-dialog ${extraDialogClass}" role="document" ${modalDialogStyle}>
                <div class="modal-content" style="width:100%">
                    ${header}
                    ${bodyContent}
                    ${footer}
                </div>
            </div>
        `;

        // Opened over another dialog (e.g. the scoring formulas): shown above it, with its own backdrop
        if (document.querySelector(".modal.show")) {
            modalEl.style.zIndex = "1065";
            modalEl.addEventListener("shown.bs.modal", () => {
                const backdrops = document.querySelectorAll<HTMLElement>(".modal-backdrop");
                const backdrop = backdrops[backdrops.length - 1];
                if (backdrop) backdrop.style.zIndex = "1060";
            }, { once: true });
        }

        document.body.prepend(modalEl);

        // remove the el when done
        modalEl.addEventListener("hidden.bs.modal", () => {
            Modal.getInstance(modalEl)?.dispose();
            modalEl.remove();
            // Bootstrap unlocks the page scroll on close, even when another dialog is still open
            if (document.querySelector(".modal.show")) document.body.classList.add("modal-open");
        });

        return modalEl;
    }
}