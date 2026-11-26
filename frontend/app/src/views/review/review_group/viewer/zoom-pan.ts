import type { MarkerArea } from '@markerjs/markerjs3';
import { Tooltip } from 'bootstrap';
import { byId } from '@examc/helpers/dom.ts';
import { currentArea, drawingArea, getPan, markerWrapper, setPan } from './area';

/**
 * Zoom and pan of the page. Both are kept across pages: the next page opens at the same
 * zoom and position as the one it replaces.
 */

const ZOOM_STEP = 0.25;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 4;

/** How much of the page always stays in view when it's moved, in pixels (all of it if it's smaller). */
const KEEP_IN_VIEW = 80;

/** 1 = the whole page fits the drawing area. */
let zoom = 1;
/** marker.js's pan offsets, in pixels; 0, 0 = centered. */
let pan = {x: 0, y: 0};

const zoomInButton = byId<HTMLButtonElement>('btn-zoom-in');
const zoomOutButton = byId<HTMLButtonElement>('btn-zoom-out');
const fitButton = byId<HTMLButtonElement>('btn-zoom-reset');

const clampRange = (value: number, limit: number): number => Math.min(limit, Math.max(-limit, value));

/**
 * Brings the page back if it's moved too far: at least KEEP_IN_VIEW pixels of it stay inside the
 * area between the floating bars. Whatever moved it (the hand tool, the wheel, marker.js's own
 * middle-button or Alt drag, a pinch), this runs right after.
 *
 * Pan 0 centers the page (marker.js centers its content) and the zoom scales it around its center,
 * so the page's center may move at most (view + page) / 2 - KEEP_IN_VIEW from the view's center.
 */
function clampPan(area: MarkerArea = currentArea()): void {
    const current = getPan(area);
    const container = area.shadowRoot?.querySelector<HTMLElement>('.canvas-container');
    if (!current || !container) return;

    // The area between the bars: the drawing surface without its padding (the bars' room)
    const style = getComputedStyle(container);
    const viewWidth = container.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    const viewHeight = container.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
    const pageWidth = area.targetWidth * area.zoomLevel;
    const pageHeight = area.targetHeight * area.zoomLevel;

    const limitX = Math.max(0, (viewWidth + pageWidth) / 2 - Math.min(KEEP_IN_VIEW, pageWidth));
    const limitY = Math.max(0, (viewHeight + pageHeight) / 2 - Math.min(KEEP_IN_VIEW, pageHeight));
    const clamped = {x: clampRange(current.x, limitX), y: clampRange(current.y, limitY)};

    if (clamped.x !== current.x || clamped.y !== current.y) setPan(area, clamped);
    pan = clamped;
}

/** Clamps once on the next frame, however many times it's asked before (for pointer moves). */
let clampFrame = 0;
function requestClampPan(): void {
    clampFrame ||= requestAnimationFrame(() => {
        clampFrame = 0;
        clampPan();
    });
}

/** Remembers an area's current pan (marker.js also pans by itself: wheel, middle button, Alt + drag). */
export function captureView(area: MarkerArea): void {
    pan = getPan(area) ?? pan;
}

/** Applies the remembered zoom and pan to an area (a new page's, once drawn). */
export function applyView(area: MarkerArea = currentArea()): void {
    area.zoomLevel = zoom;
    setPan(area, pan);
    clampPan(area);  // the new page may be smaller than the one the position was kept from
    updateZoomControls();
}

/** Sets the zoom, around the center of the drawing area (marker.js scales the pan with it). */
export function setZoom(value: number): void {
    zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(value * 1000) / 1000));
    const area = currentArea();
    area.zoomLevel = zoom;
    clampPan(area);  // zooming out of a moved page could leave it outside the view
    updateZoomControls();
}

export function zoomIn(): void {
    setZoom(zoom + ZOOM_STEP);
}

export function zoomOut(): void {
    setZoom(zoom - ZOOM_STEP);
}

/** Shows the whole page, centered. */
export function fit(): void {
    zoom = 1;
    pan = {x: 0, y: 0};
    applyView();
}

function updateZoomControls(): void {
    const label = `Fit (0), now ${Math.round(zoom * 100)}%`;
    fitButton.setAttribute('aria-label', label);
    fitButton.dataset['bsTitle'] = label;
    Tooltip.getInstance(fitButton)?.setContent({'.tooltip-inner': label});

    zoomInButton.disabled = zoom >= ZOOM_MAX;
    zoomOutButton.disabled = zoom <= ZOOM_MIN;
}

/**
 * Zooms by a wheel event: about ±20% per mouse wheel notch, and smoothly with a trackpad pinch
 * (which browsers report as Ctrl + wheel with small deltas).
 */
function zoomByWheel(event: WheelEvent): void {
    // Some mice scroll by lines instead of pixels: convert to roughly the same scale
    const delta = event.deltaMode === WheelEvent.DOM_DELTA_LINE ? event.deltaY * 33 : event.deltaY;
    setZoom(zoom * Math.exp(-delta * 0.002));
}

// ---------------------------------------------------------------------------
// Hand tool: drag to move the page
// ---------------------------------------------------------------------------

let panMode = false;
let lastPointer: {x: number; y: number} | null = null;

export function setPanMode(on: boolean): void {
    panMode = on;
    if (on) currentArea().switchToSelectMode();
}

export function init(): void {
    zoomInButton.addEventListener('click', zoomIn);
    zoomOutButton.addEventListener('click', zoomOut);
    fitButton.addEventListener('click', fit);

    // Ctrl/Cmd + wheel zooms the page, not the browser. Caught on the way down (capture), before
    // marker.js's own wheel handler, which would pan instead. A plain wheel still pans, by marker.js.
    drawingArea.addEventListener('wheel', (event) => {
        if (!(event.ctrlKey || event.metaKey)) return;
        event.preventDefault();
        event.stopPropagation();
        zoomByWheel(event);
    }, {capture: true, passive: false});

    // marker.js moves the page by itself: with the wheel (its handler has run when the event gets here)...
    drawingArea.addEventListener('wheel', () => clampPan(), {passive: true});
    // ...and with the middle button, Alt + drag or a pinch (its handlers are on window, after this one)
    window.addEventListener('pointermove', (event) => {
        if (event.buttons !== 0 || event.pointerType === 'touch') requestClampPan();
    }, {passive: true});
    window.addEventListener('pointerup', requestClampPan, {passive: true});

    // Capture phase on the wrapper, so markers are neither created nor moved while panning
    markerWrapper.addEventListener('pointerdown', (event) => {
        if (!panMode) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        lastPointer = {x: event.clientX, y: event.clientY};
        markerWrapper.setPointerCapture(event.pointerId);
        currentArea().toggleAttribute('data-panning', true);
    }, {capture: true});

    markerWrapper.addEventListener('pointermove', (event) => {
        if (!lastPointer) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const area = currentArea();
        setPan(area, {x: pan.x + event.clientX - lastPointer.x, y: pan.y + event.clientY - lastPointer.y});
        lastPointer = {x: event.clientX, y: event.clientY};
        clampPan(area);
    }, {capture: true});

    const endPan = (event: PointerEvent): void => {
        if (!lastPointer) return;
        event.stopImmediatePropagation();
        lastPointer = null;
        currentArea().toggleAttribute('data-panning', false);
    };
    markerWrapper.addEventListener('pointerup', endPan, {capture: true});
    markerWrapper.addEventListener('pointercancel', endPan, {capture: true});
}