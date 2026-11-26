import { TextMarkerEditor, type AnnotationState, type MarkerBaseEditor, type MarkerBaseState } from '@markerjs/markerjs3';
import * as api from './api';
import { config } from './config';
import { onAreaCreated } from './events';
import { setMarkedIcon } from './pages-list';
import { state } from './state';
import { currentArea } from './viewer/area';

/**
 * The page's markers: restoring them, saving them when they change, and the HighlightMarker
 * that marks the corrector box of the current grade.
 */

/** Above 0 while markers are being restored, so restoring doesn't save them back. */
let suppressPersistence = 0;
/** Lets the next save replace the page's markers with only a highlight (after "Clear all markers"). */
let allowHighlightOnlyOnce = false;

/** Applies a color to a marker editor: the text color for text, the outline for shapes. */
export function applyColorToEditor(editor: MarkerBaseEditor | undefined, color: string): void {
    if (!editor) return;
    if (editor.is(TextMarkerEditor)) {
        (editor as TextMarkerEditor).color = color;
    } else {
        editor.strokeColor = color;
    }
}

/** Shows markers in an area, without saving them back. */
export function restoreMarkers(markers: AnnotationState, area = currentArea()): void {
    suppressPersistence += 1;
    try {
        area.restoreState(markers);
    } finally {
        // marker.js may emit marker events while restoring: wait a frame before saving again
        requestAnimationFrame(() => {
            suppressPersistence = Math.max(0, suppressPersistence - 1);
        });
    }
}

function isHighlight(marker: MarkerBaseState): boolean {
    return marker.typeName === 'HighlightMarker';
}

interface SaveOptions {
    /** Save even if persistence is suppressed or nothing seems to have changed. */
    forceSave?: boolean;
    /** Allow replacing the page's markers with only a highlight. */
    allowHighlightOnly?: boolean;
    /** Allow replacing the page's markers with none. */
    allowEmpty?: boolean;
}

/** Saves the page's markers, unless nothing changed since the last save. */
export async function onMarkerChange(options: SaveOptions = {}): Promise<void> {
    const forceSave = options.forceSave === true;
    if (suppressPersistence > 0 && !forceSave) return;
    if (state.copyNo === null || state.pageNo === null) return;

    const snapshot = currentArea().getState();
    if (!forceSave && JSON.stringify(snapshot) === JSON.stringify(state.lastPersistedMarkerState)) return;

    // Never let a highlight alone replace real markers by accident
    const allowHighlightOnly = options.allowHighlightOnly === true;
    const highlightOnly = snapshot.markers.length > 0 && snapshot.markers.every(isHighlight);
    const hadRealMarkers = state.lastPersistedMarkerState?.markers.some((marker) => !isHighlight(marker)) ?? false;
    if (highlightOnly && hadRealMarkers && !allowHighlightOnlyOnce && !allowHighlightOnly) return;

    allowHighlightOnlyOnce = false;
    state.markerState = snapshot;

    const copyNo = state.copyNo;
    const pageNo = state.pageNo;
    const marked = await api.saveMarkers({
        copyNo,
        pageNo,
        rowId: state.inGroup ? String(state.entryIndex + 1) : '',
        markers: snapshot,
        scanSrc: state.scanSrc,
        allowHighlightOnly,
        allowEmpty: options.allowEmpty === true,
    });
    state.lastPersistedMarkerState = snapshot;
    setMarkedIcon(copyNo, pageNo, marked);
}

/**
 * Highlights a corrector box with a HighlightMarker (left = -1: removes the highlight).
 * Without grading schemes, highlighting the same box again removes it.
 */
export function highlightBox(left: number, top: number, width: number, height: number, persist = true): void {
    const live = currentArea().getState();
    const base = live.markers.length || !state.markerState?.markers.length ? live : state.markerState;
    const markers = [...base.markers];

    let addHighlight = true;
    for (let i = markers.length - 1; i >= 0; i--) {
        const marker = markers[i] as MarkerBaseState & {left?: number; top?: number; width?: number; height?: number};
        if (!isHighlight(marker)) continue;

        const sameBox = marker.left === left && marker.top === top && marker.width === width && marker.height === height;
        addHighlight = config.useGradingScheme || (left !== -1 && !sameBox);
        markers.splice(i, 1);
    }

    if (addHighlight && left !== -1) {
        markers.push({
            typeName: 'HighlightMarker', left, top, width, height, fillColor: 'black', opacity: 1, rotationAngle: 0,
        } as unknown as MarkerBaseState);
    }

    const next: AnnotationState = {...base, markers};
    state.markerState = next;
    restoreMarkers(next);

    if (persist) void onMarkerChange({forceSave: true, allowHighlightOnly: true});
}

/** Removes every marker except the corrector box highlight, and saves. */
export function clearMarkers(): void {
    const current = currentArea().getState();
    allowHighlightOnlyOnce = true;
    restoreMarkers({...current, markers: current.markers.filter(isHighlight)});
    requestAnimationFrame(() => void onMarkerChange({allowHighlightOnly: true, allowEmpty: true}));
}

export function init(): void {
    onAreaCreated((area) => {
        // markerchange doesn't fire for markers restored from the server, so areastatechange catches
        // their moves; the debounce merges the events of a single action into one save
        let saveTimer = 0;
        const save = (): void => {
            clearTimeout(saveTimer);
            saveTimer = window.setTimeout(() => void onMarkerChange(), 150);
        };
        area.addEventListener('markercreate', save);
        area.addEventListener('markerchange', save);
        area.addEventListener('markerdelete', save);
        area.addEventListener('areastatechange', save);

        // New markers get the drawing color (some marker types only take it once they're drawn)
        area.addEventListener('markercreate', (event) => applyColorToEditor(event.detail.markerEditor, state.drawingColor));
    });
}
