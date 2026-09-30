import './main.scss';

import { draw, zoneAt } from './drawing.ts';
import {
    canvas, nextButton, prevButton, questionMenu, root, tableElement, typeMenu,
} from './elements.ts';
import { toggleZone } from './scan.ts';
import { state } from './state.ts';
import {
    initTable, navigate, selectFirstRow, selectRow, setFilters, updateFilterLabels,
} from './table.ts';
import type { TypeFilter } from './types.ts';

document.addEventListener('DOMContentLoaded', () => {
    const table = initTable();
    table.one('draw', selectFirstRow); // show the first page once the initial data has arrived

    // Row click -> show that page
    tableElement.tBodies[0]?.addEventListener('click', (event) => {
        const row = (event.target as Element).closest('tr');
        if (row?.dataset['copy'] !== undefined) selectRow(row);
    });

    // Zone click -> toggle it
    canvas.addEventListener('click', (event) => {
        const zone = zoneAt(event.offsetX, event.offsetY);
        if (zone) void toggleZone(zone);
    });

    // Navigation
    prevButton.addEventListener('click', () => navigate(-1));
    nextButton.addEventListener('click', () => navigate(1));

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

    // Filters
    typeMenu.addEventListener('click', (event) => {
        const item = (event.target as Element).closest<HTMLElement>('[data-filter-type]');
        if (item) setFilters(item.dataset['filterType'] as TypeFilter, state.questionFilter);
    });

    questionMenu.addEventListener('click', (event) => {
        const item = (event.target as Element).closest<HTMLElement>('[data-question-id]');
        if (!item) return;
        setFilters(state.typeFilter, {
            id: Number(item.dataset['questionId']),
            name: item.dataset['questionName'] ?? '',
        });
    });

    // Redraw whenever CSS changes the canvas size; also draws the placeholder right away.
    new ResizeObserver(() => draw()).observe(canvas);

    updateFilterLabels();
    root.focus();
});