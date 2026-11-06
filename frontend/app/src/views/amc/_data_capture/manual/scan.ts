import { isExamcError } from '@examc/exceptions/shared.ts';
import { buildApiError } from '@examc/exceptions/api.ts';
import { buildFrontendError } from '@examc/exceptions/frontend.ts';
import { parseJson, postText } from '@examc/helpers/http.ts';
import type { PageShape, PageViewerElement } from '@examc/components/page-viewer/index.ts';

import type { MarkPosition, PagePosition, PageRow, ScanUrls, Zone } from './types.ts';

const PLACEHOLDER = 'Select a page in the table to show its scan.';

/** Ticked boxes are filled; flagged questions get the table badges' colours, dashed. */
const TICKED_FILL = 'rgba(13, 110, 253, 0.35)';
const OUTLINES: Record<string, Pick<PageShape, 'stroke' | 'dash' | 'strokeWidth'>> = {
    E: { stroke: '#dc3545', dash: [6, 3], strokeWidth: 3 }, // invalid
    V: { stroke: '#ffc107', dash: [6, 3], strokeWidth: 3 }, // empty
};

let viewer: PageViewerElement | null = null;
let urls: ScanUrls | null = null;
/** The page shown in the viewer. */
let current: PagePosition | null = null;
/** Incremented on every request, so responses for a page the user already left are dropped. */
let loadToken = 0;

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

/** Groups the mark corners (4 rows per zone) into one shape per zone, styled by its state. */
function toShapes(marks: MarkPosition[]): PageShape<Zone>[] {
    const byZone = new Map<number, MarkPosition[]>();
    for (const mark of marks) byZone.set(mark.zoneid, [...(byZone.get(mark.zoneid) ?? []), mark]);

    return [...byZone.values()].map((corners) => {
        corners.sort((a, b) => a.corner - b.corner);
        const first = corners[0]!;
        return {
            points: corners.flatMap((c) => [c.x, c.y]),
            data: { zoneid: first.zoneid, corner: first.corner },
            ...(first.why ? OUTLINES[first.why] : undefined),
            ...(first.checked ? { fill: TICKED_FILL } : undefined),
        };
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