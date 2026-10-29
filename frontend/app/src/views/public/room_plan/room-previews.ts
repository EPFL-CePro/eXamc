export interface RoomPreviewOptions {
    /** Called once per room block, when it is created (e.g. to make the plan clickable). */
    onCreate?: (block: HTMLElement, frame: HTMLElement, img: HTMLImageElement) => void;
    /** Called after the list of rooms changed. */
    onChange?: () => void;
}

/** "CO_1.jpg" / "CO_1.csv" -> "CO_1" */
function roomName(fileName: string): string {
    return fileName.replace(/\.[^.]+$/, "");
}

/** Both tabs: one plan in `list` per room selected in `select`. */
export function initRoomPreviews(
    select: HTMLSelectElement,
    list: HTMLElement,
    template: HTMLTemplateElement,
    mapUrl: string,
    { onCreate, onChange }: RoomPreviewOptions = {},
): void {
    /** Selected value -> its block on the page. */
    const blocks = new Map<string, HTMLElement>();

    const createBlock = (value: string): HTMLElement | null => {
        const block = template.content.firstElementChild?.cloneNode(true);
        if (!(block instanceof HTMLElement)) return null;

        const frame = block.querySelector<HTMLElement>(".room-plan-frame");
        const img = block.querySelector<HTMLImageElement>(".room-plan-frame img");
        const title = block.querySelector<HTMLElement>(".room-plan-title");
        const error = block.querySelector<HTMLElement>(".room-plan-error");
        if (!frame || !img) return null;

        const name = roomName(value);
        block.dataset.room = name;
        if (title) title.textContent = name;

        img.alt = `Plan of ${name}`;
        img.addEventListener("load", () => img.classList.remove("d-none"));
        img.addEventListener("error", () => error?.classList.remove("d-none"));
        img.src = mapUrl.replace("__file__", encodeURIComponent(name));

        onCreate?.(block, frame, img);
        return block;
    };

    /** Add blocks for newly selected rooms and remove deselected ones. */
    const sync = (): void => {
        const selected = Array.from(select.selectedOptions, (option) => option.value).filter(Boolean);

        for (const [value, block] of blocks) {
            if (!selected.includes(value)) {
                block.remove();
                blocks.delete(value);
            }
        }

        for (const value of selected) {
            const block = blocks.get(value) ?? createBlock(value);
            if (!block) continue;
            blocks.set(value, block);
            list.appendChild(block); // re-appending keeps the blocks in selection order
        }

        onChange?.();
    };

    select.addEventListener("change", sync);
    sync(); // also shows the rooms still selected after a POST re-render
}