import { byId } from '@examc/helpers/dom.ts';
import { parseJson } from '@examc/helpers/http.ts';
import * as api from './api';
import { entries, entryIndexOf, type GroupEntry } from './config';
import { onPageLoaded } from './events';
import { follow } from './pages-list';
import { state } from './state';
import { showPage } from './viewer/page-view';

/**
 * Moving between pages: the review group's pages (in the table's order), a copy's other pages,
 * the same student in other questions; and the page indicator of the bottom bar.
 */

const previousPageButton = byId<HTMLButtonElement>('btn-previous-page');
const nextPageButton = byId<HTMLButtonElement>('btn-next-page');
const pageToggle = byId<HTMLButtonElement>('btn-page-select');
const pageMenu = byId<HTMLUListElement>('page-select-menu');

/**
 * The group page last asked for. Moving by offset starts from it, not from the page shown,
 * so pressing → twice quickly moves two pages even though the first one is still loading.
 */
let requestedIndex = 0;

/** Each navigation gets a number: a newer one stops an older one that is still trying pages. */
let latestNavigation = 0;

/** Page numbers are shown without leading zeros ("Copy 2, page 12"), like in the table. */
function label(copyNo: string | number, pageNo: string | number): string {
    return `Copy ${Number(copyNo)}, page ${Number(pageNo)}`;
}

/** Keeps the URL on the page shown, so reloading reopens it. */
function updateUrl(index: number): void {
    const url = new URL(window.location.href);
    url.searchParams.set('page_id', String(index + 1));
    url.searchParams.delete('copy_no');  // one-shot: page_id takes over once the copy is resolved
    history.replaceState(history.state, '', url);
}

/**
 * Shows the review group's page at `index` (0-based, clamped). A copy another reviewer has open
 * (or a missing page) is skipped: the following pages are tried instead, wrapping around, each once.
 */
export async function goToEntry(index: number): Promise<void> {
    const total = entries.length;
    if (!total) return;

    const navigation = ++latestNavigation;
    let target = Math.min(total - 1, Math.max(0, index));

    for (let attempt = 0; attempt < total; attempt++) {
        requestedIndex = target;
        const entry = entries[target];
        if (!entry) return;
        const result = await showPage(String(entry.copy_no), String(entry.page_no));

        if (result === 'shown') {
            updateUrl(target);
            return;
        }
        if (result === 'failed' || result === 'superseded' || navigation !== latestNavigation) return;
        target = (target + 1) % total;
    }
}

/** The previous (-1) or next (1) page of the review group; nothing past the first or last one. */
export function goToPageOffset(offset: number): void {
    const target = requestedIndex + offset;
    if (target >= 0 && target < entries.length) void goToEntry(target);
}

/**
 * The previous (-1) or next (1) student: another copy, on the same page number as the
 * current one if that copy has it, else on its first page.
 */
export function goToStudentOffset(direction: -1 | 1): void {
    const current = entries[requestedIndex];
    if (!current) return;

    for (let scan = requestedIndex + direction; scan >= 0 && scan < entries.length; scan += direction) {
        const candidate = entries[scan];
        if (!candidate || String(candidate.copy_no) === String(current.copy_no)) continue;
        const copyNo = String(candidate.copy_no);

        const samePage = entries.findIndex((entry) =>
            String(entry.copy_no) === copyNo && Number(entry.page_no) === Number(current.page_no));
        void goToEntry(samePage !== -1 ? samePage : entries.findIndex((entry) => String(entry.copy_no) === copyNo));
        return;
    }
}

/** Opens a page of the copy shown; a page outside the review group is prepared by the server first. */
async function openCopyPage(copyNo: string, pageNo: string): Promise<void> {
    const index = entryIndexOf(copyNo, pageNo);
    if (index !== -1) {
        await goToEntry(index);
        return;
    }

    const navigation = ++latestNavigation;
    await api.requestCopyPage(copyNo, pageNo);
    if (navigation === latestNavigation) await showPage(copyNo, pageNo);
}

/** Opens the same student's copy in another question (the server resolves it from ?copy_no=). */
export function goToQuestion(baseUrl: string | undefined): void {
    const url = (baseUrl ?? '').trim();
    if (!url || !state.copyNo) return;
    window.location.assign(`${url}?copy_no=${encodeURIComponent(state.copyNo)}`);
}

/** The page indicator and menu of the bottom bar, for the page just loaded. */
function renderPageControls(copyNo: string, pageNo: string, copyPages: GroupEntry[], inGroup: boolean): void {
    // The indicator: which copy and page; a warning when the page isn't part of this question
    pageToggle.replaceChildren();
    if (!inGroup) {
        const warning = document.createElement('i');
        warning.className = 'fa-solid fa-triangle-exclamation text-warning me-1';
        warning.setAttribute('aria-hidden', 'true');
        pageToggle.append(warning);
    }
    pageToggle.append(label(copyNo, pageNo));
    pageToggle.dataset['bsTitle'] = inGroup
        ? `Page ${state.entryIndex + 1} of ${entries.length} in this question`
        : 'This page isn\'t part of this question';

    // The menu: the copy's pages, the ones from other questions marked
    pageMenu.replaceChildren(...copyPages.map((page) => {
        const pageCopy = String(page.copy_no);
        const pageNumber = String(page.page_no);
        const isCurrent = Number(pageNumber) === Number(pageNo);

        const item = document.createElement('a');
        item.href = '#';
        item.className = 'dropdown-item d-flex justify-content-between gap-3' + (isCurrent ? ' active' : '');
        if (isCurrent) item.setAttribute('aria-current', 'page');
        item.append(`Page ${Number(pageNumber)}`);
        if (entryIndexOf(pageCopy, pageNumber) === -1) {
            const note = document.createElement('small');
            note.className = isCurrent ? '' : 'text-body-secondary';
            note.textContent = 'other question';
            item.append(note);
        }
        item.addEventListener('click', (event) => {
            event.preventDefault();
            void openCopyPage(pageCopy, pageNumber);
        });

        const li = document.createElement('li');
        li.append(item);
        return li;
    }));

    previousPageButton.disabled = state.entryIndex <= 0;
    nextPageButton.disabled = state.entryIndex >= entries.length - 1;
}

/** Opens the page given by the URL (?page_id=, 1-based), or the first one. */
export function start(firstPage: number): void {
    void goToEntry(firstPage > 0 ? firstPage - 1 : 0);
}

export function init(): void {
    previousPageButton.addEventListener('click', () => goToPageOffset(-1));
    nextPageButton.addEventListener('click', () => goToPageOffset(1));

    // Long copies: open the page menu scrolled to the current page
    pageToggle.addEventListener('shown.bs.dropdown', () => {
        pageMenu.querySelector('.active')?.scrollIntoView({block: 'center'});
    });

    document.querySelectorAll<HTMLElement>('#btn-previous-question, #btn-next-question, .js-question-link').forEach((element) => {
        element.addEventListener('click', (event) => {
            event.preventDefault();
            goToQuestion(element.dataset['stepUrl']);
        });
    });

    onPageLoaded(({copyNo, pageNo, data, inGroup}) => {
        const copyPages = data.copy_pages ? parseJson<GroupEntry[]>(data.copy_pages) : null;
        renderPageControls(copyNo, pageNo, copyPages ?? [], inGroup);
        follow(copyNo, pageNo);
    });
}