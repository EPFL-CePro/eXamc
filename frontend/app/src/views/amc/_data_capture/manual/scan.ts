import { isExamcError } from '@examc/exceptions/shared.ts';
import { buildApiError } from '@examc/exceptions/api.ts';
import { buildFrontendError } from '@examc/exceptions/frontend.ts';
import { getJson, parseJson, postText } from '@examc/helpers/http.ts';
import type { PageShape, PageViewerElement, ViewerPage } from '@examc/components/page-viewer/index.ts';
import { AMC_CHECKED_BOX, AMC_EMPTY_BOX_FLAG, AMC_INVALID_BOX_FLAG, AMC_UNCHECKED_BOX, type AmcBoxFlag } from '@examc/helpers/amc.ts';

import type {
    MarkPosition, PagePosition, PageRow, QuestionState, QuestionStateWhy, ScanUrls, SequencePage, SequenceSlice, Zone,
} from './types.ts';

const PLACEHOLDER = 'Select a page in the table to show its scan.';
/** Pages per request to the sequence endpoint. */
const CHUNK = 50;

/** AMC's "why" codes are French: E = erreur (invalid answer), V = vide (no answer). */
const WHY_STATES: Record<QuestionStateWhy, QuestionState> = { E: 'invalid', V: 'empty' };

/** The outer frame drawn around the boxes of a flagged question. */
const FLAGS: Record<QuestionState, AmcBoxFlag> = {
    invalid: AMC_INVALID_BOX_FLAG,
    empty: AMC_EMPTY_BOX_FLAG,
};

/**
 * The viewer's document: every captured page, copy after copy. Its pages are described by the sequence
 * endpoint a chunk at a time, as the viewer needs them.
 */
interface Sequence {
    total: number;
    copyCount: number;
    /** Requests by chunk start, so each chunk is asked for once. */
    chunks: Map<number, Promise<void>>;
    /** The pages described so far, by index. */
    pages: Map<number, SequencePage>;
    /** Index of each page described so far, by "copy/page". */
    indexes: Map<string, number>;
}

let viewer: PageViewerElement | null = null;
let urls: ScanUrls | null = null;
let sequence: Sequence | null = null;
/** Incremented when the document is (re)opened or cleared, so stale answers are dropped. */
let loadToken = 0;
/** Per page, incremented on every toggle, so only the latest toggle redraws its boxes. */
const toggleTokens = new Map<number, number>();

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

const positionKey = ({ copy, page }: PagePosition): string => `${copy}/${page}`;

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

function fetchSlice(offset: number, limit: number): Promise<SequenceSlice> {
    const query = new URLSearchParams({ offset: String(offset), limit: String(limit) });
    return getJson<SequenceSlice>(`${requireUrls().sequence}?${query}`);
}

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

/** Moves each corner of a (roughly rectangular) box outwards by `by` on both axes. */
function grow(points: number[], by: number): number[] {
    const average = (axis: 0 | 1): number => {
        const values = points.filter((_, i) => i % 2 === axis);
        return values.reduce((sum, v) => sum + v, 0) / values.length;
    };
    const centre = [average(0), average(1)];
    return points.map((v, i) => v + Math.sign(v - centre[i % 2]!) * by);
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
        const box: PageShape<Zone> = { points, data, ...(first.checked ? AMC_CHECKED_BOX : AMC_UNCHECKED_BOX) };

        const flag = first.why ? FLAGS[WHY_STATES[first.why]] : undefined;
        if (!flag) return [box];

        // Drawn first, so the box stays on top (and gets the clicks inside it)
        return [{ points: grow(points, flag.gap), data, stroke: flag.stroke, strokeWidth: flag.strokeWidth }, box];
    });
}

// ---------------------------------------------------------------------------
// Sequence
// ---------------------------------------------------------------------------

/** Records a slice's pages in the sequence. */
function remember(seq: Sequence, offset: number, pages: SequencePage[]): void {
    pages.forEach((page, i) => {
        seq.pages.set(offset + i, page);
        seq.indexes.set(positionKey(page), offset + i);
    });
}

/** Describes a page of the sequence, asking for its chunk if needed. */
async function describe(seq: Sequence, index: number): Promise<SequencePage> {
    const known = seq.pages.get(index);
    if (known) return known;

    const start = Math.floor(index / CHUNK) * CHUNK;
    let chunk = seq.chunks.get(start);
    if (!chunk) {
        chunk = fetchSlice(start, CHUNK).then((slice) => remember(seq, start, slice.pages));
        chunk.catch(() => seq.chunks.delete(start)); // asked again next time
        seq.chunks.set(start, chunk);
    }
    await chunk;

    const page = seq.pages.get(index);
    if (!page) throw new Error(`Page ${index} is not in the sequence`);
    return page;
}

/** Index of a copy/page in the sequence: known already, or asked to the locate endpoint. */
async function indexOf(seq: Sequence, position: PagePosition): Promise<number> {
    const known = seq.indexes.get(positionKey(position));
    if (known !== undefined) return known;
    const { index } = await getJson<{ index: number }>(`${requireUrls().locate}?${new URLSearchParams({ ...position })}`);
    return index;
}

/** "Copy 12 / 220 · Page 2 / 6", with the AMC copy number when it isn't the copy's position. */
function pageLabel(page: SequencePage, copyCount: number): string {
    const number = page.copy_index + 1;
    const copy = String(number) === page.copy ? `Copy ${number} / ${copyCount}` : `Copy ${page.copy} (${number} / ${copyCount})`;
    return `${copy} · Page ${page.page_index + 1} / ${page.page_count}`;
}

/** Loads a page of the sequence for the viewer: its scan and boxes, label, and a divider where its copy starts. */
async function loadSequencePage(seq: Sequence, index: number): Promise<ViewerPage<Zone>> {
    const page = await describe(seq, index);
    const [image, shapes, previous] = await Promise.all([
        fetchScanUrl(page).then(loadImage),
        fetchShapes(page),
        page.page_index === 0 && index > 0 ? describe(seq, index - 1) : Promise.resolve(null),
    ]);

    const pages = `${page.page_count} page${page.page_count === 1 ? '' : 's'}`;
    return {
        image,
        shapes,
        label: pageLabel(page, seq.copyCount),
        divider: previous
            ? { end: `End of copy ${previous.copy}`, start: `Copy ${page.copy} · ${page.copy_index + 1} / ${seq.copyCount} · ${pages}` }
            : undefined,
    };
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

/**
 * Shows a page in the viewer. The viewer's document is the whole capture, copy after copy, with a divider
 * between copies: opened the first time, then only scrolled. Pages are loaded as they come near the view.
 *
 * @param {PageRow} row - The page's row data.
 */
export async function showPage(row: PageRow): Promise<void> {
    const position = { copy: String(row.copy), page: String(row.page) };
    let token = loadToken;

    try {
        if (sequence) {
            const index = await indexOf(sequence, position);
            if (token === loadToken) viewer?.scrollToPage(index);
            return;
        }

        // First page shown: open the document on it
        const openToken = token = ++loadToken;
        const first = await fetchSlice(0, CHUNK);
        const seq: Sequence = {
            total: first.total, copyCount: first.copy_count, chunks: new Map(), pages: new Map(), indexes: new Map(),
        };
        remember(seq, 0, first.pages);
        seq.chunks.set(0, Promise.resolve());
        const index = await indexOf(seq, position);
        if (openToken !== loadToken) return;

        sequence = seq;
        toggleTokens.clear();
        viewer?.showMessage(null);
        await viewer?.setPages(seq.total, (i) => loadSequencePage(seq, i), index);
    } catch (error: unknown) {
        if (token !== loadToken) return; // a newer open or a clear took over
        sequence = null;
        viewer?.clear();
        if (!isExamcError(error)) console.error(error);
        const { detail, message } = (error ?? {}) as { detail?: unknown; message?: unknown };
        viewer?.showMessage(String(detail ?? message ?? 'The scans could not be loaded.'));
    }
}

/**
 * The copy/page shown at an index of the viewer, once it's known.
 *
 * @param {number} index - The page's index in the viewer.
 * @return {PagePosition | null} Its position, or null.
 */
export function positionAt(index: number): PagePosition | null {
    const page = sequence?.pages.get(index);
    return page ? { copy: page.copy, page: page.page } : null;
}

/**
 * Toggles a box on the server, then redraws its page's boxes (the view stays as it is).
 * Rejects if the update failed.
 *
 * @param {Zone} zone - The clicked box.
 * @param {number} index - Index, in the viewer, of the page the box is on.
 * @return {Promise<PagePosition | null>} The page that changed.
 */
export async function toggleZone(zone: Zone, index: number): Promise<PagePosition | null> {
    const position = positionAt(index);
    if (!position) return null;
    const token = loadToken;
    const toggleToken = (toggleTokens.get(index) ?? 0) + 1;
    toggleTokens.set(index, toggleToken);

    await postText(requireUrls().updateZone, {
        zoneid: String(zone.zoneid),
        corner: String(zone.corner),
        ...position,
    });

    const shapes = await fetchShapes(position);
    // Same document still shown, and no later toggle on this page
    if (token === loadToken && toggleTokens.get(index) === toggleToken) viewer?.setShapes(shapes, index);
    return position;
}

/** Empties the viewer and shows the placeholder; the next page shown opens the document again. */
export function clearPage(): void {
    ++loadToken;
    sequence = null;
    viewer?.clear();
    viewer?.showMessage(PLACEHOLDER);
}