import { Popover } from 'bootstrap';
import { byId } from '@examc/helpers/dom.ts';
import { goToPageOffset, goToQuestion, goToStudentOffset } from './navigation';
import type { Tool } from './state';
import { activateTool } from './tools';
import { currentArea } from './viewer/area';
import { fit, zoomIn, zoomOut } from './viewer/zoom-pan';

/** Keyboard shortcuts, and the "?" button listing them. */

/** Shift + letter switches tools. */
const TOOL_KEYS: Record<string, Tool> = {v: 'select', t: 'text', r: 'rectangle', f: 'freehand', h: 'pan'};

const helpButton = byId<HTMLButtonElement>('btn-shortcuts');
let helpPopover: Popover | null = null;
let helpShown = false;

function toggleHelp(show = !helpShown): void {
    if (show) helpPopover?.show();
    else helpPopover?.hide();
}

/**
 * Whether a key event comes from someone typing: in a field of the page, or in a text marker's
 * editor (a <textarea> inside marker.js's shadow DOM, which the event's target alone doesn't reveal).
 */
function isTyping(event: Event): boolean {
    const origin = event.composedPath()[0];
    return origin instanceof Element && origin.matches('input, textarea, select, [contenteditable="true"]');
}

/** Whether the keys belong to something else: a dialog (comments, confirmation) or an open menu. */
function isElsewhere(event: Event): boolean {
    const target = event.target;
    return document.querySelector('.modal.show') !== null
        || (target instanceof Element && target.closest('.dropdown-menu, .dropdown-toggle.show') !== null);
}

function onKeydown(event: KeyboardEvent): void {
    if (isTyping(event) || isElsewhere(event) || event.ctrlKey || event.metaKey || event.altKey) return;

    const {key} = event;
    const toolKey = TOOL_KEYS[key.toLowerCase()];
    let handled = true;

    if (key === 'ArrowLeft' || key === 'ArrowRight') {
        const forward = key === 'ArrowRight';
        if (event.shiftKey) {
            // Same student, previous / next question
            const button = byId<HTMLButtonElement>(forward ? 'btn-next-question' : 'btn-previous-question');
            if (!button.disabled) goToQuestion(button.dataset['stepUrl']);
        } else {
            goToPageOffset(forward ? 1 : -1);
        }
    } else if (key === 'ArrowUp' || key === 'ArrowDown') {
        goToStudentOffset(key === 'ArrowDown' ? 1 : -1);
    } else if (key === '+' || key === '=') {
        zoomIn();
    } else if (key === '-') {
        zoomOut();
    } else if (key === '0') {
        fit();
    } else if (key === 'Delete' || key === 'Backspace') {
        currentArea().deleteSelectedMarkers();
    } else if (key === '?') {
        toggleHelp();
    } else if (key === 'Escape' && helpShown) {
        toggleHelp(false);
    } else if (event.shiftKey && toolKey) {
        activateTool(toolKey);
    } else {
        handled = false;
    }

    if (handled) event.preventDefault();
}

export function init(): void {
    // The list is a <template> in the page: the popover shows a copy of it
    const template = byId<HTMLTemplateElement>('shortcuts-help');
    helpPopover = new Popover(helpButton, {
        content: () => template.content.firstElementChild?.cloneNode(true) as Element,
        html: true,
        sanitize: false,  // our own markup, from the template
        trigger: 'click',
        placement: 'bottom',
        title: 'Keyboard shortcuts',
    });
    helpButton.addEventListener('shown.bs.popover', () => { helpShown = true; });
    helpButton.addEventListener('hidden.bs.popover', () => { helpShown = false; });

    // A click elsewhere closes the list
    document.addEventListener('pointerdown', (event) => {
        const target = event.target as Element;
        if (helpShown && !helpButton.contains(target) && !target.closest('.popover')) toggleHelp(false);
    });

    // Anywhere on the page, so Delete works right after selecting a marker (marker.js takes the focus)
    document.addEventListener('keydown', onKeydown);
}