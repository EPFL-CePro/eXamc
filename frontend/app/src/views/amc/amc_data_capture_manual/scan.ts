import { draw } from './drawing.ts';
import { parseJson, postText } from '@examc/helpers/http.ts';
import { state } from './state.ts';
import type { MarkPosition, PageRow, ScanUrls, Zone } from './types.ts';

let urls: ScanUrls | null = null;

class UrlsUnintialized extends Error {
    constructor() {
        super("urls object is uninitialized. Please run initScan() before referencing.");
        this.name = "UrlsUnintialized";

        // Set the prototype explicitly to maintain the correct prototype chain
        Object.setPrototypeOf(this, UrlsUnintialized.prototype);
    }
}


/** Sets the API endpoints. Called by index.ts once the DOM has loaded. */
export function initScan(endpoints: ScanUrls): void {
    urls = endpoints;
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
    if (!urls) throw new UrlsUnintialized();
    return parseJson<MarkPosition[]>(await postText(urls.marks, { copy, page })) ?? [];
}


async function fetchScanUrl(copy: string, page: string): Promise<string> {
    if (!urls) throw new UrlsUnintialized();
    const response = await fetch(`${urls.scanUrl}?${new URLSearchParams({ copy, page })}`);
    if (!response.ok) throw new Error(`Scan URL request failed: ${response.status}`);
    const { url } = (await response.json()) as { url: string };
    return url;
}

/**
 * Loads the scan and marks of a page, then draws it.
 *
 * @param {PageRow} row - The page's row data.
 */
export async function loadPage(row: PageRow): Promise<void> {
    if (!urls) throw new UrlsUnintialized();
    const token = ++state.loadToken;
    const copy = String(row.copy);
    const page = String(row.page);

    try {
        const scanPath = await fetchScanUrl(copy, page);
        const marks = await fetchMarks(copy, page);

        const image = await loadImage(scanPath);
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
    if (!urls) throw new UrlsUnintialized();

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