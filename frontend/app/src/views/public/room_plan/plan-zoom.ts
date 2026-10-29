import { PlanModal } from "./plan-modal";

/** Zoom steps, 1 = plan fits the width. */
const ZOOM_LEVELS = [1, 1.5, 2, 3, 4];

/**
 * Zoom and maximize buttons of one room.
 * Zoom: the frame gets wider and the viewport scrolls.
 * Maximize: the zoom buttons (without the maximize button) and the plan move into a PlanModal,
 * and back when it closes.
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

    const openPlanModal = (): void => {
        // Taken out rather than hidden, so the zoom buttons' group keeps its rounded corners
        maximizeButton?.remove();

        const planModal = new PlanModal(block.dataset.room ?? "", controls, viewport, onUndo, () => {
            if (maximizeButton) controls.append(maximizeButton);
            maximizeButton?.focus();
        });
        planModal.show();
    };

    // ---------- Buttons ----------

    controls.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) return;

        if (event.target.closest(".maximize-plan")) {
            openPlanModal();
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