import { byId } from '@examc/helpers/dom.ts';
import { getModal } from '@examc/helpers/modals.ts';

/**
 * Replaces the info modal's content and shows it.
 *
 * @param {...(Node | string)} content - The new content.
 */
export function showInfo(...content: (Node | string)[]): void {
    byId('ajax_info_modal_msg').replaceChildren(...content);
    getModal({ type: 'local', element: byId('ajax_info_modal') }).show();
}

/**
 * Replaces the info modal's text without reopening it (progress updates).
 *
 * @param {string} text - The new text.
 */
export function setInfoText(text: string): void {
    byId('ajax_info_modal_msg').textContent = text;
}