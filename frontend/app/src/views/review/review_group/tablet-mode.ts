import { byId } from '@examc/helpers/dom.ts';
import { emitTogglePagesList } from './events';
import { state } from './state';
import { syncToolbar } from './tools';

/**
 * Tablet mode: bigger buttons on the page (the styles are in review-group.scss), and the pages list collapsed.
 * Remembered on this device, so a tablet opens every review page in it.
 */

const STORAGE_KEY = 'examc.review.tabletMode';

const toggle = byId<HTMLInputElement>('tablet-mode-switch');
const reviewArea = byId('reviewGroup_div');

function isRemembered(): boolean {
    try {
        return localStorage.getItem(STORAGE_KEY) === '1';
    } catch {
        return false;  // storage blocked: start in the normal mode
    }
}

function remember(on: boolean): void {
    try {
        localStorage.setItem(STORAGE_KEY, on ? '1' : '0');
    } catch {
        // storage blocked: the mode just isn't remembered
    }
}

function apply(on: boolean): void {
    toggle.checked = on;
    reviewArea.classList.toggle('review-tablet', on);

    // On: the pages list collapses; off: it expands. Asked, not switched: it may already be either.
    emitTogglePagesList(on);

    // The color swatch sits under its tool's button, which just changed size.
    // The page itself is refitted by page-view's ResizeObserver: the drawing area changed width.
    syncToolbar(state.tool);
}

export function init(): void {
    apply(isRemembered());

    toggle.addEventListener('change', () => {
        remember(toggle.checked);
        apply(toggle.checked);
    });
}