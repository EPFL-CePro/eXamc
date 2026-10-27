import { ExamcModal } from "@examc/modals";

/** Zoom steps, 1 = plan fits the width. */
const ZOOM_LEVELS = [1, 1.5, 2, 3, 4];

/**
 * Large view of one room's plan: the zoom buttons and the plan move into it, with an Undo button,
 * and go back where they were once it is closed. Built when opened, removed by ExamcModal once closed.
 */
export class PlanModal extends ExamcModal {
    /**
     * @param roomName - Title of the modal.
     * @param controls - The room's zoom buttons, shown above the plan.
     * @param viewport - The room's plan.
     * @param onUndo - Called by the Undo button.
     * @param onClosed - Called once closed, when the zoom buttons and the plan are back in the room's block.
     */
    public constructor(
        roomName: string,
        controls: HTMLElement,
        viewport: HTMLElement,
        onUndo: () => void,
        onClosed: () => void,
    ) {
        super(PlanModal.createElement({
            // .room-plan-modal on the dialog: the SCSS sizes the plan's viewport inside it
            extraDialogClass: "modal-xl room-plan-modal",
            noFooter: true,
            // Undo and the zoom buttons above the plan, on the right; the toolbar goes away with the modal
            bodyContent: `
                <div class="modal-body d-flex flex-column gap-2">
                    <div class="d-flex justify-content-end gap-2" data-plan-toolbar>
                        <button type="button" class="btn btn-outline-dark btn-sm" data-plan-undo>
                            <i class="fa-solid fa-rotate-left me-1" aria-hidden="true"></i>Undo
                        </button>
                    </div>
                </div>
            `,
        }));
        // Room names come from the page, so set as text rather than as titleContent HTML
        this.setTitle(roomName);

        const body = this.element.querySelector<HTMLElement>(".modal-body");
        const toolbar = this.element.querySelector<HTMLElement>("[data-plan-toolbar]");
        if (!body || !toolbar) return;

        const controlsHome = controls.parentElement;
        const viewportHome = viewport.parentElement;

        this.element.querySelector("[data-plan-undo]")?.addEventListener("click", onUndo);
        toolbar.append(controls);
        body.append(viewport);

        this.element.addEventListener("hidden.bs.modal", () => {
            controlsHome?.append(controls);
            viewportHome?.append(viewport);
            onClosed();
        }, { once: true });
    }
}

/**
 * Zoom and maximize buttons of one room.
 * Zoom: the frame gets wider and the viewport scrolls.
 * Maximize: the zoom buttons (without the maximize button) and the plan move into a PlanModal,
 * and back when it closes.
 * `onUndo` is called by the large view's Undo button.
 */
export function setupZoom(block: HTMLElement, frame: HTMLElement, onUndo: () => void): void {
    // Parts of the copied template (they don't exist until the block is created)
    const controls = block.querySelector<HTMLElement>(".room-plan-zoom");
    const viewport = block.querySelector<HTMLElement>(".room-plan-viewport");
    const levelText = block.querySelector<HTMLElement>(".room-plan-zoom-level");
    const zoomOut = block.querySelector<HTMLButtonElement>('[data-zoom="out"]');
    const zoomIn = block.querySelector<HTMLButtonElement>('[data-zoom="in"]');
    const maximizeButton = block.querySelector<HTMLButtonElement>(".maximize-plan");
    if (!controls || !viewport) return;

    controls.classList.remove("d-none");
    let level = 0;

    const applyZoom = (nextLevel: number): void => {
        level = Math.min(Math.max(nextLevel, 0), ZOOM_LEVELS.length - 1);
        const zoom = ZOOM_LEVELS[level] ?? 1;

        // Keep the point in the middle of the view where it is
        const centerX = (viewport.scrollLeft + viewport.clientWidth / 2) / (viewport.scrollWidth || 1);
        const centerY = (viewport.scrollTop + viewport.clientHeight / 2) / (viewport.scrollHeight || 1);

        frame.style.width = `${zoom * 100}%`;

        viewport.scrollLeft = centerX * viewport.scrollWidth - viewport.clientWidth / 2;
        viewport.scrollTop = centerY * viewport.scrollHeight - viewport.clientHeight / 2;

        if (levelText) levelText.textContent = `${Math.round(zoom * 100)}%`;
        if (zoomOut) zoomOut.disabled = level === 0;
        if (zoomIn) zoomIn.disabled = level === ZOOM_LEVELS.length - 1;
    };

    // ---------- Large view ----------

    const openLargeView = (): void => {
        // Taken out rather than hidden, so the zoom buttons' group keeps its rounded corners
        maximizeButton?.remove();

        const modal = new PlanModal(block.dataset.room ?? "", controls, viewport, onUndo, () => {
            if (maximizeButton) controls.append(maximizeButton);
            maximizeButton?.focus();
        });
        modal.show();
    };

    // ---------- Buttons ----------

    controls.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) return;

        if (event.target.closest(".maximize-plan")) {
            openLargeView();
            return;
        }

        const button = event.target.closest<HTMLButtonElement>("[data-zoom]");
        switch (button?.dataset.zoom) {
            case "in":
                applyZoom(level + 1);
                break;
            case "out":
                applyZoom(level - 1);
                break;
            case "reset":
                applyZoom(0);
                break;
        }
    });

    applyZoom(0);
}