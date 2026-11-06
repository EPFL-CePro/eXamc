import { PageViewerElement } from '@examc/components/page-viewer/index.ts';
import '@examc/components/resize-handle/index.ts';
import { requireData } from '@examc/helpers/dom.ts';

import { initScan, toggleZone } from './scan.ts';
import { adjustColumns, initialPosition, initTable, markCurrentRowEdited, navigate } from './table.ts';
import type { Zone } from './types.ts';

/** Arrow keys: previous / next page of the table. */
const ARROW_STEPS: Record<string, 1 | -1> = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 };

/**
 * Wires the manual data capture: scan viewer, pages table and keyboard.
 * Does nothing when they aren't rendered (no scans imported yet).
 *
 * @param {HTMLElement} root - Fallback holder of the endpoints' data attributes (data-scan-url...),
 *     when no element around the viewer has them.
 */
export async function initManualCapture(root: HTMLElement): Promise<void> {
    const viewer = document.getElementById('scan-viewer');
    const table = document.getElementById('table-copies-pages');
    if (!(viewer instanceof PageViewerElement) || !(table instanceof HTMLTableElement)) return;

    const endpoints = viewer.closest<HTMLElement>('[data-scan-url]') ?? root;
    initScan(viewer, {
        scanUrl: requireData(endpoints, 'scanUrl'),
        marks: requireData(endpoints, 'marksUrl'),
        updateZone: requireData(endpoints, 'updateZoneUrl'),
    });

    viewer.addEventListener('shape-click', (event) => {
        toggleZone(event.detail.shape.data as Zone)
            .then(markCurrentRowEdited, (error: unknown) => console.error('Could not update the box', error));
    });

    initTable(table, await initialPosition(requireData(table, 'locateUrl')));

    viewer.addEventListener('resize-end', adjustColumns); // realign the table's header once the viewer is resized

    document.addEventListener('keydown', (event) => {
        if (event.defaultPrevented || !viewer.offsetParent) return; // handled by the viewer, or manual tab hidden
        if (event.target instanceof Element && event.target.closest('input, select, textarea, [contenteditable]')) return;
        if (viewer.handleKey(event)) return; // zoom / pan shortcuts work anywhere on the page

        const step = ARROW_STEPS[event.key];
        if (!step || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) return;
        event.preventDefault();
        navigate(step);
    });
}