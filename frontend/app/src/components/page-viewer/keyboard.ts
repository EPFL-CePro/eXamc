import type { ViewerCommand } from './types.ts';

/** Pixels moved by Shift + arrow keys. */
const PAN_STEP = 80;

const PAN_KEYS: Record<string, [number, number]> = {
    ArrowLeft: [PAN_STEP, 0], ArrowRight: [-PAN_STEP, 0], ArrowUp: [0, PAN_STEP], ArrowDown: [0, -PAN_STEP],
};

const PAGE_KEYS: Record<string, 'previous' | 'next' | 'first' | 'last'> = {
    PageUp: 'previous', PageDown: 'next', Home: 'first', End: 'last',
};

/**
 * The command of a shortcut: + / - zoom, 0 fit, Shift + arrows pan, Page Up / Down, Home / End pages.
 *
 * @param {KeyboardEvent} event - A keydown event.
 * @return {ViewerCommand | null} The command, or null if the key isn't a shortcut.
 */
export function keyCommand(event: KeyboardEvent): ViewerCommand | null {
    if (event.ctrlKey || event.metaKey || event.altKey) return null;

    const pan = event.shiftKey ? PAN_KEYS[event.key] : undefined;
    if (pan) return { type: 'pan', dx: pan[0], dy: pan[1] };

    const page = PAGE_KEYS[event.key];
    if (page) return { type: 'page', to: page };

    switch (event.key) {
        case '+': case '=': return { type: 'zoom-in' };
        case '-': case '_': return { type: 'zoom-out' };
        case '0': return { type: 'fit' };
        default: return null;
    }
}