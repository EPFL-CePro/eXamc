import { Tooltip } from 'bootstrap';
import * as api from './api';
import { config } from './config';
import { onPageLoaded } from './events';
import { highlightBox } from './markers';
import { setMarkedIcon } from './pages-list';
import { state } from './state';
import { highlightCorrectorBox } from './viewer/corrector-boxes';

/**
 * The grading schemes card: its tabs (and their locks), the panel loaded by htmx for the page's copy,
 * the marks, and the student's note.
 */

const tabsList = document.getElementById('review-scheme-tabs');

function tabs(): HTMLButtonElement[] {
    return [...(tabsList?.querySelectorAll<HTMLButtonElement>('.js-scheme-link') ?? [])];
}

function schemeIdOf(tab: HTMLButtonElement): string {
    return tab.id.replace('review-scheme-link-', '');
}

/**
 * Locks or unlocks a scheme tab: a locked tab can't be clicked or focused, and its wrapper's
 * tooltip says why. Tabs the template disabled (invalid schemes) are left as they are.
 */
function setTabLocked(tab: HTMLButtonElement, locked: boolean, message = ''): void {
    if (tab.dataset.invalid === 'true') return;

    tab.disabled = locked;
    tab.setAttribute('aria-disabled', String(locked));
    tab.tabIndex = locked ? -1 : 0;

    const wrapper = tab.parentElement;
    if (!wrapper) return;
    const tooltip = Tooltip.getInstance(wrapper);
    if (locked) {
        wrapper.tabIndex = 0;
        if (tooltip) tooltip.setContent({'.tooltip-inner': message});
        else new Tooltip(wrapper, {title: message, placement: 'bottom'});
    } else {
        tooltip?.dispose();
        wrapper.removeAttribute('tabindex');
    }
}

/** The copy has points in this scheme: every other scheme is locked. */
function lockOtherSchemes(schemeId: string): void {
    const used = document.getElementById(`review-scheme-link-${schemeId}`);
    const name = used?.textContent?.trim() ?? 'another grading scheme';
    const message = `This copy is already graded with "${name}". Remove its marks to switch grading scheme.`;
    tabs().forEach((tab) => setTabLocked(tab, tab !== used, message));
}

/** The copy has no points: every scheme can be chosen. */
function unlockAllSchemes(): void {
    tabs().forEach((tab) => setTabLocked(tab, false));
}

function setActiveTab(schemeId: string): void {
    tabs().forEach((tab) => {
        const active = schemeIdOf(tab) === schemeId;
        tab.classList.toggle('active', active);
        tab.setAttribute('aria-selected', String(active));
    });
}

/** Blocks the schemes (with an overlay) while the page shown isn't part of the review group. */
function setSchemesBlocked(blocked: boolean): void {
    const overlay = document.getElementById('grading-scheme-block-overlay');
    if (overlay) overlay.style.display = blocked ? 'flex' : 'none';
}

/** Shows "Graded" or "Ungraded" next to a scheme's points. */
function setGradedStatus(schemeId: string, graded: boolean): void {
    const status = document.getElementById(`gsc-status-${schemeId}`);
    if (!status) return;
    status.textContent = graded ? 'Graded' : 'Ungraded';
    status.classList.toggle('text-bg-success', graded);
    status.classList.toggle('text-bg-secondary', !graded);
}

/** The afterSwap handler of the latest scheme request; replaced (and removed) by the next one. */
let pendingSchemeSwap: ((event: Event) => void) | null = null;

/**
 * Loads a scheme's panel for the copy shown (from a tab click, or to refresh it).
 * NOTE: global, for the tabs' inline onclick.
 */
export function sendScheme(tab: HTMLButtonElement, event?: Event): boolean {
    event?.preventDefault();
    event?.stopPropagation();

    if (tab.disabled || state.copyNo === null) return false;

    // The URL's last segment is the copy number
    const url = (tab.getAttribute('hx-get') ?? '').replace(/\/[^/?#]+(?=[?#]|$)/, `/${encodeURIComponent(state.copyNo)}`);
    tab.setAttribute('hx-get', url);

    // Select the clicked tab right away; the response may move the selection to the scheme actually used
    setActiveTab(schemeIdOf(tab));

    if (pendingSchemeSwap) document.body.removeEventListener('htmx:afterSwap', pendingSchemeSwap);

    const onAfterSwap = (swap: Event): void => {
        const detail = (swap as CustomEvent).detail;
        // Only the panel loaded by this request (not the checkbox panel loaded from inside it, not an older one)
        if (detail?.target?.id !== 'review-scheme-panel' || detail.requestConfig?.elt !== tab) return;

        document.body.removeEventListener('htmx:afterSwap', onAfterSwap);
        pendingSchemeSwap = null;

        const xhr: XMLHttpRequest | undefined = detail.xhr;
        const usedId = xhr?.getResponseHeader('X-Used-Grading-Scheme-Id');
        const corrBoxIndex = xhr?.getResponseHeader('X-Corr-Box-Index');
        const points = Number(xhr?.getResponseHeader('X-Points'));

        // A copy graded with a scheme stays on it; otherwise the clicked scheme is the one used
        const lockedOn = points > 0 && usedId ? usedId : null;
        const activeId = lockedOn ?? schemeIdOf(tab);

        if (activeId !== state.gradingSchemeId) checkboxesScroll = 0;  // another scheme: start at the top
        state.gradingSchemeId = activeId;

        if (lockedOn) lockOtherSchemes(lockedOn);
        else unlockAllSchemes();
        setActiveTab(activeId);

        if (corrBoxIndex != null) highlightCorrectorBox(Number(corrBoxIndex));
    };

    pendingSchemeSwap = onAfterSwap;
    document.body.addEventListener('htmx:afterSwap', onAfterSwap);

    void htmx.ajax('GET', url, {target: '#review-scheme-panel', swap: 'innerHTML transition:true', source: tab});
    return false;
}

/** Reloads the selected scheme's panel (or the first usable one's) for the copy shown. */
export function refreshActiveScheme(): void {
    const tab = tabsList?.querySelector<HTMLButtonElement>('.js-scheme-link.active:not(:disabled)')
        ?? tabsList?.querySelector<HTMLButtonElement>('.js-scheme-link:not(:disabled)');
    if (tab) setTimeout(() => sendScheme(tab), 0);
}

/** Reloads a scheme's checkbox panel (it also refreshes the full / zero points buttons). */
function reloadCheckboxPanel(schemeId: string): void {
    const panel = document.getElementById(`chk-panel-${schemeId}`);
    const url = panel?.getAttribute('hx-get');
    if (panel && url) void htmx.ajax('GET', url, {target: panel, swap: 'innerHTML'});
}

/**
 * A mark was ticked or unticked, an adjustment changed, or a full / zero points button clicked.
 * NOTE: global, for the inline onchange / onclick of the checkboxes template.
 */
export async function updatePagesGroupCheckBox(
    itemId: string, checked: boolean | null, adjustment: string | null, zero: boolean, full: boolean,
): Promise<void> {
    let isChecked = checked;
    let adjustmentValue = adjustment;

    if (adjustment !== null) {
        // An adjustment: sent with its checkbox's state
        isChecked = document.querySelector<HTMLInputElement>(`#${itemId.replace('adj', 'check')}`)?.checked ?? null;
    } else {
        // A checkbox: sent with its adjustment, if it has one
        adjustmentValue = document.querySelector<HTMLInputElement>(`#${itemId.replace('check', 'adj')}`)?.value ?? null;
    }

    const response = await api.updateCheckBox({
        item_id: itemId,
        copy_nr: state.copyNo,
        checked: isChecked,
        adjustment: adjustmentValue,
        grading_scheme_id: state.gradingSchemeId,
        zero,
        full,
    });
    if (response === '' || state.gradingSchemeId === null) return;

    const [corrBoxIndex, points, maxPoints, marked] = JSON.parse(response) as [number, number | '', number, boolean?];
    const schemeId = state.gradingSchemeId;

    if (marked !== undefined && state.copyNo !== null && state.pageNo !== null) {
        setMarkedIcon(state.copyNo, state.pageNo, Boolean(marked));
        setGradedStatus(schemeId, Boolean(marked));
    }

    if (points !== '') {
        const pointsElement = document.getElementById(`gsc-points-${schemeId}`);
        if (pointsElement) pointsElement.textContent = `${Number(points).toFixed(2)} / ${Number(maxPoints).toFixed(2)}`;

        if (Number(points) > 0) lockOtherSchemes(schemeId);
        else unlockAllSchemes();
    }

    if (corrBoxIndex === -1) highlightBox(-1, -1, -1, -1);
    else highlightCorrectorBox(corrBoxIndex);

    reloadCheckboxPanel(schemeId);
}

// ---------------------------------------------------------------------------
// The student's note
// ---------------------------------------------------------------------------

function setNoteStatus(textarea: HTMLTextAreaElement, message: string, isError = false): void {
    const status = textarea.closest('.mb-1')?.querySelector('.js-student-report-note-status');
    if (!status) return;
    status.textContent = message;
    status.classList.toggle('text-danger', isError);
}

/** Remembers each note's saved text, so leaving a note unchanged doesn't save it again. */
function initNoteFields(root: ParentNode): void {
    root.querySelectorAll<HTMLTextAreaElement>('.js-student-report-note').forEach((field) => {
        field.dataset.lastSavedValue = field.value;
    });
}

/** Saves a student's note. NOTE: global, for the templates. */
export async function saveStudentReportNote(textarea: HTMLTextAreaElement): Promise<void> {
    const pagesGroupId = textarea.dataset.pagesGroupId;
    const content = textarea.value;
    if (textarea.disabled || !pagesGroupId || !state.copyNo) return;
    if (textarea.dataset.lastSavedValue === content) return;

    setNoteStatus(textarea, 'Saving…');
    try {
        await api.saveStudentNote(pagesGroupId, state.copyNo, content);
        textarea.dataset.lastSavedValue = content;
        setNoteStatus(textarea, 'Saved');
    } catch {
        setNoteStatus(textarea, 'Save failed', true);
    }
}

// ---------------------------------------------------------------------------
// htmx swaps
// ---------------------------------------------------------------------------

/** The checkboxes' scroll position, kept across their reloads (ticks and page changes). */
let checkboxesScroll = 0;

function initHtmxHooks(): void {
    document.body.addEventListener('htmx:beforeSwap', (event) => {
        const target: Element = (event as CustomEvent).detail.target;

        // A tooltip visible when its element is replaced would stay stuck on screen
        target.querySelectorAll('[data-bs-title], [data-bs-toggle="tooltip"]').forEach((element) => {
            Tooltip.getInstance(element)?.dispose();
        });

        const list = document.getElementById('review-grading-scheme-checkboxes-dt');
        if (list && target.contains(list)) checkboxesScroll = list.scrollTop;
    });

    document.body.addEventListener('htmx:afterSwap', (event) => {
        const target: Element = (event as CustomEvent).detail.target;

        const list = document.getElementById('review-grading-scheme-checkboxes-dt');
        if (list && target.contains(list)) list.scrollTop = checkboxesScroll;

        initNoteFields(target);
    });
}

export function init(): void {
    // Tabs disabled by the template are invalid schemes: the graded lock never unlocks them
    tabs().filter((tab) => tab.disabled).forEach((tab) => { tab.dataset.invalid = 'true'; });

    initHtmxHooks();
    initNoteFields(document);

    // Notes are saved when the field is left
    document.body.addEventListener('change', (event) => {
        const target = event.target;
        if (target instanceof HTMLTextAreaElement && target.classList.contains('js-student-report-note')) {
            void saveStudentReportNote(target);
        }
    });

    if (config.useGradingScheme) {
        onPageLoaded(({inGroup}) => {
            setSchemesBlocked(!inGroup);
            refreshActiveScheme();
        });
    }
}
