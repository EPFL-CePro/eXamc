import DataTable from 'datatables.net-bs5';
import 'datatables.net-bs5/css';
import { setupDatatables } from '@examc/helpers/datatables.ts';
import { byId } from '@examc/helpers/dom.ts';
import { onTogglePagesList } from './events';

/** The pages table on the left: it follows the page shown, and opens a page when its row is clicked. */

const table = byId<HTMLTableElement>('table-copies-pages');

/** The row of a page of the review group (null for a page outside it). */
function rowOf(copyNo: string, pageNo: string): HTMLTableRowElement | null {
    return document.getElementById(`copy_${copyNo}_${pageNo}`) as HTMLTableRowElement | null;
}

/** An element of a page's row, by suffix; page numbers may be written with or without leading zeros. */
function rowPart(copyNo: string, pageNo: string, suffix: string): HTMLElement | null {
    return document.getElementById(`copy_${copyNo}_${pageNo}_${suffix}`)
        ?? document.getElementById(`copy_${copyNo}_${Number(pageNo)}_${suffix}`);
}

let highlighted: HTMLTableRowElement | null = null;

/**
 * Highlights the row of the page shown, and scrolls the table to it. For a page outside the
 * review group, the last group page's row stays highlighted.
 */
export function follow(copyNo: string, pageNo: string): void {
    const row = rowOf(copyNo, pageNo);
    if (!row) return;

    if (row !== highlighted) {
        // table-primary, not table-active: the hover color would look the same
        highlighted?.classList.remove('table-primary');
        highlighted?.removeAttribute('aria-current');
        row.classList.add('table-primary');
        row.setAttribute('aria-current', 'true');
        highlighted = row;
    }
    row.scrollIntoView({block: 'nearest'});
}

/** Shows or hides the lock on a page's row (another reviewer has its copy open). */
export function setLocked(copyNo: string, pageNo: string, locked: boolean): void {
    const icon = rowPart(copyNo, pageNo, 'id');
    if (icon) icon.style.display = locked ? 'inline-block' : 'none';
}

/** Shows or hides the "graded" check on a page's row. */
export function setMarkedIcon(copyNo: string, pageNo: string, marked: boolean): void {
    const cell = rowPart(copyNo, pageNo, 'marked');
    if (!cell) return;
    cell.innerHTML = marked
        ? '<i class="fa-solid fa-circle-check fa-lg" aria-hidden="true"></i><span class="visually-hidden">Graded</span>'
        : '';
    cell.dataset.order = marked ? '1' : '0';
}

/**
 * Collapses the list into a narrow vertical strip, or expands it back.
 * @param collapse true collapses, false expands, undefined switches; asking for the current state does nothing.
 */
function setCollapsed(collapse?: boolean): void {
    const body = byId('pages-group-list-table-div');
    const isCollapsed = body.classList.contains('d-none');
    const collapsed = collapse ?? !isCollapsed;
    // Done twice, the width saved on collapse would be overwritten by the strip's own
    if (collapsed === isCollapsed) return;

    body.classList.toggle('d-none', collapsed);
    byId('expand-collapse-group-list-bt').setAttribute('aria-expanded', String(!collapsed));
    byId('expand-group-list-icon').classList.toggle('d-none', !collapsed);
    byId('collapse-group-list-icon').classList.toggle('d-none', collapsed);

    // Collapsed: the header becomes a narrow vertical strip, expand button on top, title rotated
    const header = byId('pages-group-list-header');
    header.classList.toggle('flex-column-reverse', collapsed);   // the button (last in the markup) on top
    header.classList.toggle('justify-content-end', collapsed);
    header.classList.toggle('justify-content-between', !collapsed);
    header.classList.toggle('flex-grow-1', collapsed);           // the strip runs the full card height
    header.classList.toggle('border-bottom-0', collapsed);
    header.classList.toggle('px-1', collapsed);
    header.classList.toggle('py-2', collapsed);
    header.classList.toggle('py-1', !collapsed);

    // Reads bottom to top, like a spine label
    const title = byId('pages-group-list-title');
    title.style.writingMode = collapsed ? 'vertical-rl' : '';
    title.style.transform = collapsed ? 'rotate(180deg)' : '';

    // The strip is as narrow as its content; the dragged width comes back on expand
    const list = byId('pages-group-list');
    if (collapsed) {
        list.dataset.expandedStyle = list.style.cssText;
        list.style.width = 'auto';
        list.style.minWidth = '0';
    } else {
        list.style.cssText = list.dataset.expandedStyle ?? '';
    }
    byId('pages-group-list-resize').classList.toggle('d-none', collapsed);
}

/**
 * @param onRowClick Opens the page at a position of the review group (0-based), when its row is clicked.
 */
export function init(onRowClick: (index: number) => void): void {
    setupDatatables();
    if (!DataTable.isDataTable(table)) {
        new DataTable(table, {
            autoWidth: true,
            layout: {topStart: null, topEnd: null, bottomStart: 'info', bottomEnd: null},
            lengthChange: false,
            order: [[0, 'asc']],
            paging: false,
        });
    }

    table.addEventListener('click', (event) => {
        const row = (event.target as Element).closest<HTMLTableRowElement>('tr[data-index]');
        if (row) onRowClick(Number(row.dataset.index));
    });

    // Collapsed or expanded by whoever sends the event (emitTogglePagesList)
    onTogglePagesList(setCollapsed);
}