import { draw } from './drawing.ts';
import { urls } from './elements.ts';
import { parseJson, parseScanPath, postText } from './http.ts';
import { state } from './state.ts';
import type { MarkPosition, Zone } from './types.ts';

/**
 * Turns a scan file path into the URL it is served from.
 *
 * @param {string} path - The scan path.
 * @return {string} The scan URL.
 */
function toScanUrl(path: string): string {
    const parts = path.split('/');
    return `/${parts[1] ?? ''}/${parts[3] ?? ''}`;
}

/**
 * Loads an image.
 *
 * @param {string} src - The image URL.
 * @return {Promise<HTMLImageElement>} The loaded image.
 */
function loadImage(src: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error(`Failed to load ${src}`));
        image.src = src;
    });
}

/**
 * Fetches the mark positions of a page.
 *
 * @param {string} copy - The copy number.
 * @param {string} page - The page number.
 * @return {Promise<MarkPosition[]>} The mark corners, 4 per zone.
 */
async function fetchMarks(copy: string, page: string): Promise<MarkPosition[]> {
    return parseJson<MarkPosition[]>(await postText(urls.marks, { copy, page })) ?? [];
}

/**
 * Loads the scan and marks of the page in a table row, then draws it.
 *
 * @param {HTMLTableRowElement} row - A row with `data-copy`, `data-page` and `data-questions`.
 */
export async function loadPage(row: HTMLTableRowElement): Promise<void> {
    const token = ++state.loadToken;
    const copy = row.dataset['copy'] ?? '';
    const page = row.dataset['page'] ?? '';
    const questions = row.dataset['questions'] ?? '';

    try {
        let scanPath: string;
        let marks: MarkPosition[] = [];

        if (questions.includes('/scans/extra/')) {
            // Extra pages have no mark zones; the field holds the scan path itself.
            scanPath = questions;
        } else {
            scanPath = parseScanPath(await postText(urls.scanUrl, { copy, page }));
            marks = await fetchMarks(copy, page);
        }

        const image = await loadImage(toScanUrl(scanPath));
        if (token !== state.loadToken) return;

        state.view = { copy, page, image, marks };
        draw();
    } catch (error) {
        if (token === state.loadToken) console.error(error);
    }
}

/**
 * Toggles a zone on the server, then refreshes the marks and redraws.
 *
 * @param {Zone} zone - The zone to toggle.
 */
export async function toggleZone(zone: Zone): Promise<void> {
    if (!state.view) return;
    const { copy, page } = state.view;
    const token = ++state.loadToken;

    try {
        await postText(urls.updateZone, {
            zoneid: String(zone.zoneid),
            corner: String(zone.corner),
            copy,
            page,
        });
        const marks = await fetchMarks(copy, page);
        if (token !== state.loadToken || !state.view) return;

        state.view.marks = marks;
        draw();
    } catch (error) {
        console.error(error);
    }
}

/** Forgets the current page and shows the placeholder. */
export function clearPage(): void {
    ++state.loadToken; // drop any load still in flight
    state.view = null;
    draw();
}