import { downloadPlans } from "./plan-export";
import { setupZoom } from "./plan-zoom";
import { initRoomPreviews } from "./room-previews";

type NumberingMode = "numbers" | "letters" | "prefix";

export interface ManualTabElements {
    select: HTMLSelectElement;
    list: HTMLElement;
    form: HTMLFormElement;
    numberingInputs: HTMLInputElement[];
    prefixInput: HTMLInputElement;
    downloadButton: HTMLButtonElement;
    undoButton: HTMLButtonElement;
    exportLayout: HTMLElement;
}

function toNumberingMode(value: string | undefined): NumberingMode {
    return value === "letters" || value === "prefix" ? value : "numbers";
}

/** 0 -> A, 25 -> Z, 26 -> AA, ... */
function numberToLetters(index: number): string {
    let letters = "";
    let n = index + 1;
    while (n > 0) {
        const rem = (n - 1) % 26;
        letters = String.fromCharCode(65 + rem) + letters;
        n = Math.floor((n - 1) / 26);
    }
    return letters;
}

/** Manual tab: room previews + click on a plan to place seat labels, then download the plans. */
export function initManualTab(el: ManualTabElements, template: HTMLTemplateElement, mapUrl: string, fileName: string): void {
    const { list, prefixInput, downloadButton, undoButton, exportLayout } = el;

    // Nothing is sent to the server from this tab: pressing Enter in the prefix field must not reload the page
    el.form.addEventListener("submit", (event) => event.preventDefault());

    /** Labels in the order they were placed, for Undo. */
    let placed: HTMLDivElement[] = [];

    /** Each room's frame, by block: while its large view is open, the frame is outside the list. */
    const frames = new Map<Element, HTMLElement>();

    let numberingMode = toNumberingMode(el.numberingInputs.find((input) => input.checked)?.value);

    const labelText = (index: number): string => {
        switch (numberingMode) {
            case "letters":
                return numberToLetters(index);
            case "prefix":
                return `${prefixInput.value}${index + 1}`;
            case "numbers":
                return String(index + 1);
        }
    };

    /**
     * Number every label: rooms in selection order, and inside a room in the order
     * the labels were placed. Numbering continues from one room to the next.
     */
    const relabelAll = (): void => {
        let index = 0;
        for (const block of list.children) {
            frames.get(block)?.querySelectorAll<HTMLDivElement>(".print-label").forEach((label) => {
                label.textContent = labelText(index++);
            });
        }
    };

    const placeLabel = (frame: HTMLElement, img: HTMLImageElement, event: MouseEvent): void => {
        const rect = img.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const percentX = (x / rect.width) * 100;
        const percentY = (y / rect.height) * 100;

        const label = document.createElement("div");
        label.className = "print-label";
        label.style.left = `${percentX}%`;
        label.style.top = `${percentY}%`;
        label.dataset.x = String(x);
        label.dataset.y = String(y);
        label.dataset.percentX = String(percentX);
        label.dataset.percentY = String(percentY);

        frame.appendChild(label);
        placed.push(label);
        relabelAll();
    };

    /** Remove the last placed label (Undo buttons and Ctrl+Z). */
    const undo = (): void => {
        placed.pop()?.remove();
        relabelAll();
    };

    initRoomPreviews(el.select, list, template, mapUrl, {
        onCreate: (block, frame, img) => {
            frames.set(block, frame);
            img.addEventListener("click", (event) => placeLabel(frame, img, event));
            setupZoom(block, frame, undo);
        },
        onChange: () => {
            // Labels of deselected rooms are gone with their block
            placed = placed.filter((label) => label.isConnected);
            for (const block of frames.keys()) {
                if (!block.isConnected) frames.delete(block);
            }
            relabelAll();
        },
    });

    // ---------- Events ----------

    downloadButton.addEventListener("click", () => {
        downloadButton.disabled = true;
        void downloadPlans(list, exportLayout, fileName).finally(() => {
            downloadButton.disabled = false;
        });
    });

    undoButton.addEventListener("click", undo);

    // Ctrl+Z (Cmd+Z on Mac), also in the large view
    document.addEventListener("keydown", (event) => {
        if (event.key.toLowerCase() !== "z" || !(event.ctrlKey || event.metaKey) || event.shiftKey || event.altKey) return;
        if (list.offsetParent === null) return; // Manual tab not shown
        // Typing in a field (e.g. the prefix): keep the browser's own undo
        if (event.target instanceof HTMLElement && event.target.closest("input, textarea, select, [contenteditable]")) return;

        event.preventDefault();
        undo();
    });

    for (const input of el.numberingInputs) {
        input.addEventListener("change", () => {
            numberingMode = toNumberingMode(input.value);
            prefixInput.classList.toggle("d-none", numberingMode !== "prefix");
            relabelAll();
        });
    }

    prefixInput.addEventListener("input", relabelAll);
    prefixInput.classList.toggle("d-none", numberingMode !== "prefix");
}