import './main.scss';

import { byId, requireData } from '@examc/helpers/dom.ts';
import { draw, initDrawing, zoneAt } from './drawing.ts';
import { initScan, toggleZone } from './scan.ts';
import { initTable, navigate, selectRow } from './table.ts';

document.addEventListener('DOMContentLoaded', () => {
    const root = byId('amc-data-capture');
    const canvas = byId<HTMLCanvasElement>('canvas-scan');
    const tableElement = byId<HTMLTableElement>('table-copies-pages');

    initDrawing(canvas);
    initScan({
        scanUrl: requireData(root, 'scanUrl'),
        marks: requireData(root, 'marksUrl'),
        updateZone: requireData(root, 'updateZoneUrl'),
    });
    initTable(tableElement);

    tableElement.tBodies[0]?.addEventListener('click', (event) => {
        const row = (event.target as Element).closest('tr');
        if (row) selectRow(row);
    });

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

    new ResizeObserver(() => draw()).observe(canvas);
    root.focus();
});