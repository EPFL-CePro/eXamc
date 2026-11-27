import type { MarkerBaseEditor } from '@markerjs/markerjs3';
import { byId, isTyping } from './dom';
import { onAreaCreated, onAreaShown } from './events';
import { refreshActiveScheme } from './grading-schemes';
import { applyColorToEditor, clearMarkers } from './markers';
import { state, type Tool } from './state';
import { currentArea, drawingArea, markerWrapper } from './viewer/area';
import { setPanMode } from './viewer/zoom-pan';

/** The drawing tools: their buttons, the cursor, the color swatch, Delete and "Clear all markers". */

const toolbar = byId('mjs-tools');
const buttons: Record<Tool, HTMLButtonElement> = {
    select: byId<HTMLButtonElement>('btn-pointer'),
    text: byId<HTMLButtonElement>('btn-text-marker'),
    rectangle: byId<HTMLButtonElement>('btn-frame-marker'),
    freehand: byId<HTMLButtonElement>('btn-freehand-marker'),
    pan: byId<HTMLButtonElement>('btn-pan'),
};

/** The marker.js marker each drawing tool creates. */
const MARKER_TYPES: Partial<Record<Tool, string>> = {
    text: 'TextMarker',
    rectangle: 'FrameMarker',
    freehand: 'FreehandMarker',
};

/** Cursor around the page for each tool (inside marker.js, its stylesheet sets it from data-tool). */
const CURSORS: Partial<Record<Tool, string>> = {
    text: 'text',
    rectangle: 'crosshair',
    freehand: 'crosshair',
    pan: 'grab',
};

const colorSwatch = byId('color-swatch');
const colorButton = byId<HTMLButtonElement>('btn-color');
const colorInput = byId<HTMLInputElement>('color-input');

/**
 * Shows which tool is active: its button, the color swatch for marker tools, the pan mode and the cursor.
 * Doesn't start drawing (see activateTool).
 */
export function syncToolbar(tool: Tool = 'select'): void {
    state.tool = tool;

    toolbar.querySelectorAll('.btn').forEach((button) => button.classList.remove('active'));
    buttons[tool].classList.add('active');

    setPanMode(tool === 'pan');
    showColorSwatch(tool in MARKER_TYPES ? buttons[tool] : null);

    currentArea().dataset.tool = tool;
    markerWrapper.style.cursor = CURSORS[tool] ?? '';
}

/** Switches to a tool, like clicking its button: a marker tool starts drawing a marker. */
export function activateTool(tool: Tool): void {
    const area = currentArea();
    const markerType = MARKER_TYPES[tool];

    if (markerType) {
        applyColorToEditor(area.createMarker(markerType), state.drawingColor);
    } else {
        area.switchToSelectMode();
    }
    syncToolbar(tool);
}

/** Shows the color swatch centered under a tool button, filled with the drawing color; null hides it. */
function showColorSwatch(toolButton: HTMLButtonElement | null): void {
    colorSwatch.classList.toggle('d-none', !toolButton);
    if (!toolButton) return;

    // The picker starts from the drawing color, not the last selected marker's
    colorInput.value = state.drawingColor;
    colorButton.style.backgroundColor = state.drawingColor;

    // Positions relative to the drawing area, which the swatch is placed in
    const area = drawingArea.getBoundingClientRect();
    const tools = toolbar.getBoundingClientRect();
    const tool = toolButton.getBoundingClientRect();
    const size = colorSwatch.offsetHeight;

    colorSwatch.style.left = `${tool.left - area.left + (tool.width - size) / 2}px`;
    colorSwatch.style.top = `${tools.bottom - area.top + 6}px`;
}

export function init(): void {
    (Object.entries(buttons) as [Tool, HTMLButtonElement][]).forEach(([tool, button]) => {
        button.addEventListener('click', () => activateTool(tool));
    });

    // The color: kept for the next markers, and applied to the one being drawn
    state.drawingColor = colorInput.value;
    colorButton.addEventListener('click', (event) => {
        event.stopPropagation();
        colorInput.click();
    });
    colorInput.addEventListener('input', () => {
        state.drawingColor = colorInput.value;
        colorButton.style.backgroundColor = state.drawingColor;
        applyColorToEditor(currentArea().currentMarkerEditor, state.drawingColor);
    });

    byId('btn-clear').addEventListener('click', () => {
        clearMarkers();
        requestAnimationFrame(() => refreshActiveScheme());
    });

    // Delete / Backspace remove the selected markers, except while typing (in a text marker or a field)
    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Delete' && event.key !== 'Backspace') return;
        if (isTyping(event)) return;
        currentArea().deleteSelectedMarkers();
        event.preventDefault();
    });

    onAreaCreated((area) => {
        // The toolbar keeps the tool; it's started on the new page once that page is drawn (onAreaShown)
        syncToolbar(state.tool);

        // marker.js returns to select mode after drawing a marker, except freehand (continuous drawing)
        area.addEventListener('markercreate', (event) => {
            const editor: MarkerBaseEditor = event.detail.markerEditor;
            if (!editor.continuousCreation) syncToolbar('select');
        });
    });

    // The page is drawn: a marker tool starts drawing on it again (a page whose scan failed is read-only)
    onAreaShown((area) => {
        if (!area.inert) activateTool(state.tool);
    });
}