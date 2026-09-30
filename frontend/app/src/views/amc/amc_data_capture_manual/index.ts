import './main.scss';

import { draw, zoneAt } from './drawing.ts';
import { canvas, root, tableElement } from './elements.ts';
import { toggleZone } from './scan.ts';
import { initTable, navigate, selectRow } from './table.ts';

document.addEventListener('DOMContentLoaded', () => {
    // Filters live in the table headers (ColumnControl); the first row is selected once data arrives.
    initTable();

    // Row click -> show that page
    tableElement.tBodies[0]?.addEventListener('click', (event) => {
        const row = (event.target as Element).closest('tr');
        if (row) selectRow(row);
    });

    // Zone click -> toggle it
    canvas.addEventListener('click', (event) => {
        const zone = zoneAt(event.offsetX, event.offsetY);
        if (zone) void toggleZone(zone);
    });

    root.addEventListener('keydown', (event) => {
        switch (event.key) {
            case 'ArrowLeft':
            case 'ArrowUp':
                event.preventDefault();
                navigate(-1);
                break;
            case 'ArrowRight':
            case 'ArrowDown':
                event.preventDefault();
                navigate(1);
                break;
        }
    });

    // Redraw whenever CSS changes the canvas size; also draws the placeholder right away.
    new ResizeObserver(() => draw()).observe(canvas);

    root.focus();
});