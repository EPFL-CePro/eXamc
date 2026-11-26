import { MarkerArea, type AnnotationState } from '@markerjs/markerjs3';
import { byId } from '@examc/helpers/dom.ts';
import { describeFailure, parseJson, toScanUrl } from '@examc/helpers/http.ts';
import { showToast } from '@examc/helpers/toasts.ts';
import * as api from '../api';
import { entryIndexOf } from '../config';
import { emitAreaCreated, emitPageLoaded } from '../events';
import { restoreMarkers } from '../markers';
import { setLocked } from '../pages-list';
import { state } from '../state';
import { currentArea, drawingArea, markerWrapper, setCurrentArea, setVisibleArea, visibleArea } from './area';
import { drawCorrectorBoxes, setCorrectorBoxes, type CorrectorBoxCorner } from './corrector-boxes';
import { applyView, captureView } from './zoom-pan';

/**
 * Showing a page: each page gets a new MarkerArea, built hidden beneath the one on screen and
 * swapped in once its page is drawn, so changing page never flashes a blank area.
 */

/**
 * Styles inside marker.js's shadow DOM, which ignores the page's CSS:
 * - the drawing surface fills the whole area (marker.js sizes it to the page, hence !important),
 *   with room above and below for the floating bars (--bars-room, set when the page is fitted);
 * - the page, on white with a shadow, stands out from the area around it (Bootstrap's own shadow:
 *   its custom properties reach into the shadow DOM);
 * - the tool cursors, driven by data-tool / data-panning on the MarkerArea element.
 *   Select mode isn't listed, so marker.js keeps its own move and resize cursors there.
 */
const markerAreaSheet = new CSSStyleSheet();
markerAreaSheet.replaceSync(`
    .canvas-container {
        height: 100% !important;
        box-sizing: border-box;
        padding-block: var(--bars-room, 0px);
    }

    /* The scan, scaled and moved with the page by marker.js's transform (so is its shadow) */
    .canvas-container > div > img {
        background-color: #fff;
        box-shadow: var(--bs-box-shadow, 0 0.5rem 1rem rgba(0, 0, 0, 0.15));
    }

    :host([data-tool="text"]) .canvas-container,
    :host([data-tool="text"]) .canvas-container * { cursor: text !important; }

    :host([data-tool="rectangle"]) .canvas-container,
    :host([data-tool="rectangle"]) .canvas-container *,
    :host([data-tool="freehand"]) .canvas-container,
    :host([data-tool="freehand"]) .canvas-container * { cursor: crosshair !important; }

    :host([data-tool="pan"]) .canvas-container,
    :host([data-tool="pan"]) .canvas-container * { cursor: grab !important; }

    :host([data-panning]) .canvas-container,
    :host([data-panning]) .canvas-container * { cursor: grabbing !important; }
`);

const HIDDEN = {position: 'absolute', inset: '0', visibility: 'hidden', zIndex: '-1'};
const SHOWN = {position: '', inset: '', visibility: '', zIndex: ''};

/** The scan of the page shown; laying the page out waits for it to load. */
const sourceImage = new Image();

function installSheet(area: MarkerArea): void {
    const root = area.shadowRoot;
    if (root && !root.adoptedStyleSheets.includes(markerAreaSheet)) {
        root.adoptedStyleSheets = [...root.adoptedStyleSheets, markerAreaSheet];
    }
}

/** Creates the next page's MarkerArea, hidden beneath the one on screen. */
function createHiddenArea(): MarkerArea {
    // A newer page replaces one still loading
    if (currentArea() !== visibleArea()) currentArea().remove();

    // The page on screen stays, read-only, until the new one is drawn
    const previous = visibleArea();
    previous.style.pointerEvents = 'none';
    captureView(previous);

    const area = new MarkerArea();
    Object.assign(area.style, HIDDEN);
    markerWrapper.appendChild(area);
    installSheet(area);
    setCurrentArea(area);
    emitAreaCreated(area);
    return area;
}

/** Shows the new MarkerArea and removes the one it replaces. */
function reveal(area: MarkerArea): void {
    if (area !== currentArea() || area === visibleArea()) return;
    visibleArea().remove();
    Object.assign(area.style, SHOWN);
    setVisibleArea(area);
}

const nextFrame = (): Promise<void> => new Promise((resolve) => requestAnimationFrame(() => resolve()));

/**
 * Resolves once the image is loaded and decoded, so showing it can't flash a blank or half-drawn page.
 * Also resolves if the image fails: better to show what there is than to stay hidden.
 */
async function imageReady(img: HTMLImageElement): Promise<void> {
    if (!(img.complete && img.naturalWidth > 0)) {
        await new Promise((resolve) => {
            img.addEventListener('load', resolve, {once: true});
            img.addEventListener('error', resolve, {once: true});
        });
    }
    await img.decode().catch(() => undefined);
}

/** Waits for marker.js to draw the page, applies the view and corrector boxes, then reveals the area. */
async function revealWhenDrawn(area: MarkerArea): Promise<void> {
    // marker.js inserts its own <img> once the target image is set
    let img: HTMLImageElement | null = null;
    for (let tries = 20; tries > 0 && !img; tries--) {
        img = area.shadowRoot?.querySelector<HTMLImageElement>('.canvas-container > div img') ?? null;
        if (!img) await nextFrame();
    }
    if (img) await imageReady(img);
    if (area !== currentArea()) return;  // a newer page took over while this one loaded

    applyView(area);
    drawCorrectorBoxes(sourceImage.naturalWidth);

    // Swap on the next frame, once the view and the boxes are applied
    await nextFrame();
    reveal(area);
}

/** Fits the page in the drawing area, clear of the floating bars, then reveals it once drawn. */
function layout(): void {
    const area = currentArea();

    // marker.js fills the drawing area; the page is fitted inside it, clear of the top and bottom bars.
    // Zooming and panning can still move the page under them.
    const barsRoom = Math.max(byId('mjs-tools').offsetHeight, byId('mjs-toolbar-nav').offsetHeight) + 16;
    area.style.width = '100%';
    area.style.height = '100%';
    area.style.setProperty('--bars-room', `${barsRoom}px`);

    const rect = drawingArea.getBoundingClientRect();
    const imageRatio = (sourceImage.naturalWidth || 1) / (sourceImage.naturalHeight || 1);
    const availableWidth = rect.width - 20;
    const availableHeight = rect.height - 2 * barsRoom;

    // As wide as the area allows, unless that makes the page too tall
    let width = availableWidth;
    let height = width / imageRatio;
    if (availableHeight > 0 && height > availableHeight) {
        height = availableHeight;
        width = height * imageRatio;
    }

    // The size first: marker.js sizes the page from it when the image is set
    area.targetWidth = width;
    area.targetHeight = height;
    area.targetImage = sourceImage;

    void revealWhenDrawn(area);
}

/**
 * The scan couldn't be loaded: the page is shown without it, read-only (markers drawn on a blank
 * page would be saved at the wrong size), and the reviewer is told.
 */
function onScanError(): void {
    const area = currentArea();
    if (area === visibleArea()) return;  // nothing waiting for this scan

    showToast(
        `The scan of copy ${Number(state.copyNo)}, page ${Number(state.pageNo)} couldn't be loaded. `
        + 'Its markers can\'t be edited; reload the page to try again.',
        {error: true},
    );
    area.inert = true;
    reveal(area);
}

/** Loads the scan into the area being prepared (lays it out right away if it's already loaded). */
function loadScan(src: string): void {
    if (sourceImage.getAttribute('src') === src && sourceImage.complete && sourceImage.naturalWidth > 0) {
        layout();
    } else {
        sourceImage.src = src;
    }
}

/** What became of a request to show a page. */
export type ShowResult =
    | 'shown'
    | 'locked'       // another reviewer has the copy open
    | 'missing'      // the server has no such page
    | 'failed'       // the server couldn't be reached, or answered with an error (a toast says so)
    | 'superseded';  // another page was requested meanwhile

/** Each request to show a page gets a number; only the latest one is shown. */
let latestRequest = 0;

/** A page's data, read and checked: everything showPage needs. */
interface DecodedPage {
    copyNo: string;
    pageNo: string;
    scanSrc: string;
    markers: AnnotationState;
    correctorBoxes: CorrectorBoxCorner[];
}

/**
 * Reads the server's page data. copyPageUrl is "<prefix>/<folder>/<prefix>_<copy>_<page>/<file>":
 * the copy and page actually loaded come from its third segment.
 *
 * @throws {Error} If the data isn't what the page expects (malformed JSON included).
 */
function decodePage(data: api.PageData): DecodedPage {
    const location = data.copyPageUrl?.split('/')[2];
    const [, copyNo, pageNo] = location?.split('_') ?? [];
    if (!copyNo || !pageNo) {
        throw new Error(`unexpected scan path "${data.copyPageUrl}"`);
    }

    return {
        copyNo,
        pageNo,
        scanSrc: toScanUrl(data.copyPageUrl),
        // A page without markers yet: the server sends null, read as an empty annotation
        markers: (data.markers ? parseJson<AnnotationState>(data.markers) : null)
            ?? {version: 3, width: 0, height: 0, markers: []},
        correctorBoxes: (data.corrector_boxes ? parseJson<CorrectorBoxCorner[]>(data.corrector_boxes) : null) ?? [],
    };
}

/** Shows a copy's page (in the review group or not). */
export async function showPage(copyNo: string, pageNo: string): Promise<ShowResult> {
    const request = ++latestRequest;
    let data: api.PageData | null;

    try {
        const locked = await api.isCopyLocked(copyNo);
        if (request !== latestRequest) return 'superseded';
        setLocked(copyNo, pageNo, locked);
        if (locked) return 'locked';

        data = await api.fetchPage(copyNo, pageNo);
    } catch (error) {
        if (request === latestRequest) {
            const {status} = describeFailure(error);
            showToast(
                `Copy ${Number(copyNo)}, page ${Number(pageNo)} couldn't be loaded `
                + (status ? `(server error ${status}).` : ': the server can\'t be reached.'),
                {error: true},
            );
        }
        return 'failed';
    }
    if (request !== latestRequest) return 'superseded';
    if (!data) return 'missing';

    // Checked before anything changes on screen: unusable data leaves the current page as it is
    let page: DecodedPage;
    try {
        page = decodePage(data);
    } catch (error) {
        console.error('Page data from the server', data, error);
        showToast(`Copy ${Number(copyNo)}, page ${Number(pageNo)} couldn't be read: the server sent unexpected data.`, {error: true});
        return 'failed';
    }

    const area = createHiddenArea();
    const index = entryIndexOf(page.copyNo, page.pageNo);

    state.copyNo = page.copyNo;
    state.pageNo = page.pageNo;
    state.inGroup = index !== -1;
    if (state.inGroup) state.entryIndex = index;
    state.scanSrc = page.scanSrc;
    state.markerState = page.markers;
    state.lastPersistedMarkerState = page.markers;
    setCorrectorBoxes(page.correctorBoxes);

    emitPageLoaded({copyNo: page.copyNo, pageNo: page.pageNo, data, inGroup: state.inGroup});

    restoreMarkers(page.markers, area);
    loadScan(page.scanSrc);
    return 'shown';
}

/** Refits the page shown to the drawing area's new size, with its current markers (no reload). */
function relayout(): void {
    if (state.copyNo === null) return;

    // A page still loading has no markers in its area yet (marker.js restores them once its image
    // is loaded): take the ones it was given, or they'd be lost, then saved as empty
    const loading = currentArea() !== visibleArea();
    const markers = loading && state.markerState ? state.markerState : currentArea().getState();
    const area = createHiddenArea();
    restoreMarkers(markers, area);  // marker.js rescales them to the new page size
    layout();
}

export function init(): void {
    // The first, empty MarkerArea, replaced by the first page's
    const first = currentArea();
    markerWrapper.appendChild(first);
    installSheet(first);
    emitAreaCreated(first);

    // The next page is placed in the same spot, beneath the visible one (z-index -1): keep that inside the wrapper
    markerWrapper.style.isolation = 'isolate';

    sourceImage.addEventListener('load', layout);
    sourceImage.addEventListener('error', onScanError);

    // While a panel is dragged, wait for the drop instead of refitting on every frame
    let dragging = false;
    document.addEventListener('resize-start', () => { dragging = true; });
    document.addEventListener('resize-end', () => {
        dragging = false;
        relayout();
    });

    // Refit when the drawing area changes size (window resize, the pages list collapsing...)
    let timer = 0;
    let lastSize = '';
    new ResizeObserver((entries) => {
        const entry = entries[0];
        if (!entry) return;
        const size = `${Math.round(entry.contentRect.width)}x${Math.round(entry.contentRect.height)}`;
        if (size === lastSize) return;
        const first = lastSize === '';
        lastSize = size;
        if (first || dragging) return;

        clearTimeout(timer);
        timer = window.setTimeout(relayout, 150);
    }).observe(drawingArea);
}