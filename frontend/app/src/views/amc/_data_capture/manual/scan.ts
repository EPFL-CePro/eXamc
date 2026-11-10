import { isExamcError } from '@examc/exceptions/shared.ts';
import { buildApiError } from '@examc/exceptions/api.ts';
import { buildFrontendError } from '@examc/exceptions/frontend.ts';
import { parseJson, postText } from '@examc/helpers/http.ts';
import type { PageShape, PageViewerElement } from '@examc/components/page-viewer/index.ts';

import type { MarkPosition, PagePosition, PageRow, ScanUrls, Zone } from './types.ts';

const PLACEHOLDER = 'Select a page in the table to show its scan.';
/**
 * AMC's colours. Box: thin blue frame, red when ticked. Around the boxes of a flagged
 * question, a thicker outer frame: yellow = invalid answer (e.g. two boxes ticked),
 * light blue = no box ticked.
 */
const BOX = {
    unchecked: { stroke: '#33a3ff', strokeWidth: 1 },
    checked: { stroke: '#ff0000', strokeWidth: 3 },
};
const FLAG_COLOURS: Record<string, string> = { E: '#ffff33', V: '#00ffff' };
const FLAG_FRAME = { strokeWidth: 5, gap: 4 }; // gap: between box and frame, in scan pixels



let viewer: PageViewerElement | null = null;
let urls: ScanUrls | null = null;
/** The page shown in the viewer. */
let current: PagePosition | null = null;
/** Incremented on every request, so responses for a page the user already left are dropped. */
let loadToken = 0;

/** Moves each corner of a (roughly rectangular) box outwards by `by` on both axes. */
function grow(points: number[], by: number): number[] {
    const average = (axis: 0 | 1): number => {
        const values = points.filter((_, i) => i % 2 === axis);
        return values.reduce((sum, v) => sum + v, 0) / values.length;
    };
    const centre = [average(0), average(1)] as const;
    return points.map((v, i) => v + Math.sign(v - centre[i % 2 as 0 | 1]) * by);
}

/** Sets the viewer and the API endpoints, and shows the placeholder. */
export function initScan(pageViewer: PageViewerElement, endpoints: ScanUrls): void {
    viewer = pageViewer;
    urls = endpoints;
    viewer.showMessage(PLACEHOLDER);
}

function requireUrls(): ScanUrls {
    if (!urls) throw new Error('initScan() must be called first');
    return urls;
}

// ---------------------------------------------------------------------------
// Requests
// ---------------------------------------------------------------------------

function loadImage(src: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(buildFrontendError({ detail: `Failed to load ${src}` }));
        image.src = src;
    });
}

async function fetchScanUrl({ copy, page }: PagePosition): Promise<string> {
    const response = await fetch(`${requireUrls().scanUrl}?${new URLSearchParams({ copy, page })}`);
    const data = (await response.json()) as { url?: string; detail?: string };

    if (!response.ok) throw buildApiError({ detail: data.detail ?? `Scan URL request failed: ${response.status}` });
    if (!data.url) throw buildApiError({ type: 'wrong-api-response', detail: "'url' key is missing in the server's response" });
    return data.url;
}

async function fetchShapes({ copy, page }: PagePosition): Promise<PageShape<Zone>[]> {
    const marks = parseJson<MarkPosition[]>(await postText(requireUrls().marks, { copy, page })) ?? [];
    return toShapes(marks);
}


/** One shape per box, plus an outer frame under it when its question is flagged. */
function toShapes(marks: MarkPosition[]): PageShape<Zone>[] {
    const byZone = new Map<number, MarkPosition[]>();
    for (const mark of marks) byZone.set(mark.zoneid, [...(byZone.get(mark.zoneid) ?? []), mark]);

    return [...byZone.values()].flatMap((corners) => {
        corners.sort((a, b) => a.corner - b.corner);
        const first = corners[0]!;
        const points = corners.flatMap((c) => [c.x, c.y]);
        const data = { zoneid: first.zoneid, corner: first.corner };
        const box: PageShape<Zone> = { points, data, ...(first.checked ? BOX.checked : BOX.unchecked) };

        const flag = first.why ? FLAG_COLOURS[first.why] : undefined;
        if (!flag) return [box];
        // Drawn first, so the box stays on top (and gets the clicks inside it)
        return [{ points: grow(points, FLAG_FRAME.gap), data, stroke: flag, strokeWidth: FLAG_FRAME.strokeWidth }, box];
    });
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

/**
 * Loads a page's scan and boxes into the viewer.
 *
 * @param {PageRow} row - The page's row data.
 */
export async function loadPage(row: PageRow): Promise<void> {
    const token = ++loadToken;
    const position = { copy: String(row.copy), page: String(row.page) };

    try {
        const [image, shapes] = await Promise.all([fetchScanUrl(position).then(loadImage), fetchShapes(position)]);
        if (token !== loadToken) return;

        current = position;
        viewer?.showMessage(null);
        viewer?.setImage(image);
        viewer?.setShapes(shapes);
    } catch (error: unknown) {
        if (token !== loadToken) return;
        current = null;
        viewer?.clear();
        if (!isExamcError(error)) console.error(error);
        const { detail, message } = (error ?? {}) as { detail?: unknown; message?: unknown };
        viewer?.showMessage(String(detail ?? message ?? 'The scan could not be loaded.'));
    }
}

/**
 * Toggles a box on the server, then redraws the page's boxes (the scan and zoom stay as they are).
 * Rejects if the update failed.
 *
 * @param {Zone} zone - The clicked box.
 */
export async function toggleZone(zone: Zone): Promise<void> {
    if (!current) return;
    const position = current;
    const token = ++loadToken;

    await postText(requireUrls().updateZone, {
        zoneid: String(zone.zoneid),
        corner: String(zone.corner),
        ...position,
    });

    const shapes = await fetchShapes(position);
    if (token === loadToken) viewer?.setShapes(shapes);
}

/** Empties the viewer and shows the placeholder. */
export function clearPage(): void {
    ++loadToken;
    current = null;
    viewer?.clear();
    viewer?.showMessage(PLACEHOLDER);
}