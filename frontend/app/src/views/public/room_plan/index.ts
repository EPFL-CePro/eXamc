import { Tab, Tooltip } from "bootstrap";
import { zipSync } from "fflate";

import "./room-plan.scss";
import html2canvas from "html2canvas-pro";

type NumberingMode = "numbers" | "letters" | "prefix";

const EXPORT_WIDTH = "1000px";

/** Zoom steps of the Manual tab, 1 = plan fits the width. */
const ZOOM_LEVELS = [1, 1.5, 2, 3, 4];

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

/** "CO_1.jpg" / "CO_1.csv" -> "CO_1" */
function roomName(fileName: string): string {
    return fileName.replace(/\.[^.]+$/, "");
}

function saveBlob(blob: Blob, fileName: string): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
}

// ---------------------------------------------------------------------------
// Room previews (both tabs): one plan per room selected in the pane's select
// ---------------------------------------------------------------------------

interface RoomPreviewOptions {
    /** Called once per room block, when it is created (e.g. to make the plan clickable). */
    onCreate?: (block: HTMLElement, frame: HTMLElement, img: HTMLImageElement) => void;
    /** Called after the list of rooms changed. */
    onChange?: () => void;
}

/** Returns the element holding the room blocks, or null if the pane is incomplete. */
function initRoomPreviews(
    pane: HTMLElement,
    template: HTMLTemplateElement,
    mapUrl: string,
    { onCreate, onChange }: RoomPreviewOptions = {},
): HTMLElement | null {
    const select = pane.querySelector<HTMLSelectElement>("select[data-room-select]");
    const list = pane.querySelector<HTMLElement>(".room-plans");
    const emptyMessage = pane.querySelector<HTMLElement>(".room-plans-empty");
    if (!select || !list || !emptyMessage) {
        console.error(`Room plan (#${pane.id}): the room select or the preview list is missing.`);
        return null;
    }

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

        emptyMessage.classList.toggle("d-none", selected.length > 0);
        onChange?.();
    };

    select.addEventListener("change", sync);
    sync(); // also shows the rooms still selected after a POST re-render
    return list;
}

// ---------------------------------------------------------------------------
// Default tab: room previews + show/hide form rows depending on the options
// ---------------------------------------------------------------------------

function initDefaultTab(pane: HTMLElement, template: HTMLTemplateElement, mapUrl: string): void {
    initRoomPreviews(pane, template, mapUrl);

    const form = pane.querySelector<HTMLFormElement>("#default-form");
    if (!form) return;

    const checkedValue = (name: string): string | undefined =>
        form.querySelector<HTMLInputElement>(`input[name="${name}"]:checked`)?.value;

    const toggleRow = (fieldName: string, show: boolean): void => {
        form.querySelector(`#div-${fieldName}`)?.classList.toggle("d-none", !show);
    };

    /** The special file is needed when skipping seats or using special numbering. */
    const showHideSpecialFile = (): void => {
        toggleRow(
            "special_file",
            checkedValue("skipping_option") === "skip" || checkedValue("numbering_option") === "special",
        );
    };

    /** "Last seat number" is irrelevant when all seats are filled. */
    const showHideLastNumber = (): void => {
        const fillAll = form.querySelector<HTMLInputElement>('input[name="fill_all_seats"]');
        toggleRow("last_seat_number", !fillAll?.checked);
    };

    form.addEventListener("change", (event) => {
        if (!(event.target instanceof HTMLInputElement)) return;

        switch (event.target.name) {
            case "skipping_option":
            case "numbering_option":
                showHideSpecialFile();
                break;
            case "fill_all_seats":
                showHideLastNumber();
                break;
        }
    });

    // Initial state (also correct after a POST re-render)
    showHideSpecialFile();
    showHideLastNumber();
}

// ---------------------------------------------------------------------------
// Special tab: room previews + click on a plan to place seat labels
// ---------------------------------------------------------------------------

function initSpecialTab(pane: HTMLElement, template: HTMLTemplateElement, mapUrl: string, fileName: string): void {
    // The special form is rendered with prefix="special", so its fields are "special-<name>"
    const numberingName = "special-numbering_option";

    const exportLayout = document.querySelector<HTMLDivElement>("#export-layout");
    const prefixInput = pane.querySelector<HTMLInputElement>("#prefix-input");
    const downloadButton = pane.querySelector<HTMLButtonElement>("#btn-download-plans");
    const undoButton = pane.querySelector<HTMLButtonElement>("#btn-undo-label");
    if (!exportLayout || !prefixInput || !downloadButton || !undoButton) {
        console.error("Room plan (special tab): an element of the page is missing.");
        return;
    }

    // Nothing is sent to the server from this tab: pressing Enter in the prefix field must not reload the page
    pane.querySelector<HTMLFormElement>("form")?.addEventListener("submit", (event) => event.preventDefault());

    /** Labels in the order they were placed, for Undo. */
    let placed: HTMLDivElement[] = [];

    let numberingMode = toNumberingMode(
        pane.querySelector<HTMLInputElement>(`input[name="${numberingName}"]:checked`)?.value,
    );

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
        pane.querySelectorAll<HTMLDivElement>(".room-plans .print-label").forEach((label, index) => {
            label.textContent = labelText(index);
        });
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

    /** Zoom buttons of one room: the frame gets wider and the viewport scrolls. */
    const setupZoom = (block: HTMLElement, frame: HTMLElement): void => {
        const controls = block.querySelector<HTMLElement>(".room-plan-zoom");
        const viewport = block.querySelector<HTMLElement>(".room-plan-viewport");
        const levelText = block.querySelector<HTMLElement>(".room-plan-zoom-level");
        const zoomOut = block.querySelector<HTMLButtonElement>('[data-zoom="out"]');
        const zoomIn = block.querySelector<HTMLButtonElement>('[data-zoom="in"]');
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

        controls.addEventListener("click", (event) => {
            const button = event.target instanceof Element ? event.target.closest<HTMLButtonElement>("[data-zoom]") : null;
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
    };

    const list = initRoomPreviews(pane, template, mapUrl, {
        onCreate: (block, frame, img) => {
            img.addEventListener("click", (event) => placeLabel(frame, img, event));
            setupZoom(block, frame);
        },
        onChange: () => {
            // Labels of deselected rooms are gone with their block
            placed = placed.filter((label) => label.isConnected);
            relabelAll();
        },
    });
    if (!list) return;

    // ---------- Download ----------

    const renderRoom = async (block: HTMLElement): Promise<Blob | null> => {
        const frame = block.querySelector<HTMLElement>(".room-plan-frame");
        const img = frame?.querySelector("img");
        if (!frame || !img || img.classList.contains("d-none")) return null; // plan not loaded

        const clone = frame.cloneNode(true);
        if (!(clone instanceof HTMLElement)) return null;
        clone.style.width = EXPORT_WIDTH;
        exportLayout.replaceChildren(clone);

        const canvas = await html2canvas(clone);
        return new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    };

    /** One room: a JPG. Several rooms: a ZIP with one JPG per room. */
    const downloadPlans = async (): Promise<void> => {
        const images: { name: string; blob: Blob }[] = [];

        try {
            for (const block of list.querySelectorAll<HTMLElement>(".room-plan")) {
                const blob = await renderRoom(block);
                if (blob) images.push({ name: `${block.dataset.room ?? "plan"}.jpg`, blob });
            }
        } finally {
            exportLayout.replaceChildren();
        }

        const [first] = images;
        if (!first) return;

        if (images.length === 1) {
            saveBlob(first.blob, `${fileName}.jpg`);
            return;
        }

        // JPGs are already compressed, so store them as-is (level 0)
        const files: Record<string, Uint8Array> = {};
        for (const { name, blob } of images) {
            files[name] = new Uint8Array(await blob.arrayBuffer());
        }
        const zipped = zipSync(files, { level: 0 });
        saveBlob(new Blob([new Uint8Array(zipped)], { type: "application/zip" }), `${fileName}.zip`);
    };

    // ---------- Events ----------

    downloadButton.addEventListener("click", () => {
        downloadButton.disabled = true;
        void downloadPlans().finally(() => {
            downloadButton.disabled = false;
        });
    });

    undoButton.addEventListener("click", () => {
        placed.pop()?.remove();
        relabelAll();
    });

    pane.addEventListener("change", (event) => {
        if (event.target instanceof HTMLInputElement && event.target.name === numberingName) {
            numberingMode = toNumberingMode(event.target.value);
            prefixInput.classList.toggle("d-none", numberingMode !== "prefix");
            relabelAll();
        }
    });

    prefixInput.addEventListener("input", relabelAll);
    prefixInput.classList.toggle("d-none", numberingMode !== "prefix");
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function init(): void {
    const page = document.querySelector<HTMLElement>("#rooms-plans-page");
    if (!page) return;

    page.querySelectorAll<HTMLElement>('[data-bs-toggle="tooltip"]')
        .forEach((el) => Tooltip.getOrCreateInstance(el));

    // Open the tab the server asked for
    const tabButton = page.querySelector<HTMLButtonElement>(`#${page.dataset.currentTab || "default"}-tab`)
        ?? page.querySelector<HTMLButtonElement>("#default-tab");
    if (tabButton) Tab.getOrCreateInstance(tabButton).show();

    const template = page.querySelector<HTMLTemplateElement>("#room-plan-template");
    const mapUrl = page.dataset.mapUrl;
    if (!template || !mapUrl) {
        console.error("Room plan: #room-plan-template or data-map-url is missing.");
        return;
    }

    const defaultPane = page.querySelector<HTMLElement>("#pills-default");
    if (defaultPane) initDefaultTab(defaultPane, template, mapUrl);

    const specialPane = page.querySelector<HTMLElement>("#pills-special");
    if (specialPane) initSpecialTab(specialPane, template, mapUrl, page.dataset.fileName || "plan");
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}