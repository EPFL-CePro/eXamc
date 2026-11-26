import { MarkerArea } from '@markerjs/markerjs3';
import { byId } from '../dom';

/** The drawing area, and the wrapper the MarkerAreas are placed in. */
export const drawingArea = byId('mjsapp');
export const markerWrapper = byId('marker-wrapper');

/**
 * The MarkerArea of the page being shown or loaded (`current`), and the one on screen (`visible`).
 * They differ while the next page loads: it stays hidden beneath the visible one until it's drawn.
 */
let current = new MarkerArea();
let visible = current;

export function currentArea(): MarkerArea {
    return current;
}

export function visibleArea(): MarkerArea {
    return visible;
}

export function setCurrentArea(area: MarkerArea): void {
    current = area;
}

export function setVisibleArea(area: MarkerArea): void {
    visible = area;
}

/** marker.js's transformed stage (zoom and pan apply to it), inside its shadow DOM. */
export function getMarkerStage(area: MarkerArea = current): HTMLElement | null {
    return area.shadowRoot?.querySelector<HTMLElement>('.canvas-container > div') ?? null;
}

/**
 * marker.js's pan offsets and transform are private, but zooming around the page needs them.
 * Every use goes through here, so a marker.js update that changes them breaks in one place.
 */
interface PanInternals {
    _panX: number;
    _panY: number;
    applyTransform(): void;
}

export function getPan(area: MarkerArea): {x: number; y: number} | null {
    const internals = area as unknown as Partial<PanInternals>;
    return typeof internals._panX === 'number' && typeof internals._panY === 'number'
        ? {x: internals._panX, y: internals._panY}
        : null;
}

export function setPan(area: MarkerArea, pan: {x: number; y: number}): void {
    const internals = area as unknown as Partial<PanInternals>;
    if (typeof internals.applyTransform !== 'function') return;
    internals._panX = pan.x;
    internals._panY = pan.y;
    internals.applyTransform.call(area);
}
