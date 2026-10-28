import { zipSync } from "fflate";
import html2canvas from "html2canvas-pro";

const EXPORT_WIDTH = "1000px";

function saveBlob(blob: Blob, fileName: string): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** One room's plan with its labels as a JPG, rendered at a fixed width. Null if the plan is not loaded. */
async function renderRoom(block: HTMLElement, exportLayout: HTMLElement): Promise<Blob | null> {
    const frame = block.querySelector<HTMLElement>(".room-plan-frame");
    const img = block.querySelector<HTMLImageElement>(".room-plan-frame img");
    if (!frame || !img || img.classList.contains("d-none")) return null;

    const clone = frame.cloneNode(true);
    if (!(clone instanceof HTMLElement)) return null;
    clone.style.width = EXPORT_WIDTH;
    exportLayout.replaceChildren(clone);

    const canvas = await html2canvas(clone);
    return new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
}

/** One room: a JPG. Several rooms: a ZIP with one JPG per room. */
export async function downloadPlans(list: HTMLElement, exportLayout: HTMLElement, fileName: string): Promise<void> {
    const images: { name: string; blob: Blob }[] = [];

    try {
        for (const block of list.querySelectorAll<HTMLElement>(".room-plan")) {
            const blob = await renderRoom(block, exportLayout);
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
}