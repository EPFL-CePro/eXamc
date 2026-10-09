import { byId } from '@examc/helpers/dom.ts';
import { getModal } from '@examc/helpers/modals.ts';

/**
 * Replaces the info modal's content and shows it.
 *
 * @param {...(Node | string)} content - The new content.
 */
export function showInfo(...content: (Node | string)[]): void {
    byId('ajax-info-modal-msg').replaceChildren(...content);
    getModal({ type: 'local', element: byId('ajax-info-modal') }).show();
}

/**
 * Replaces the info modal's text without reopening it (progress updates).
 *
 * @param {string} text - The new text.
 */
export function setInfoText(text: string): void {
    byId('ajax-info-modal-msg').textContent = text;
}