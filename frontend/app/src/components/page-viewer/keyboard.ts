import type { ViewerCommand } from './types.ts';

/** Pixels moved by Shift + arrow keys. */
const PAN_STEP = 80;

const PAN_KEYS: Record<string, [number, number]> = {
    ArrowLeft: [PAN_STEP, 0], ArrowRight: [-PAN_STEP, 0], ArrowUp: [0, PAN_STEP], ArrowDown: [0, -PAN_STEP],
};

/**
 * The command of a shortcut: + / - zoom, 0 whole page, Shift + arrows pan.
 *
 * @param {KeyboardEvent} event - A keydown event.
 * @return {ViewerCommand | null} The command, or null if the key isn't a shortcut.
 */
export function keyCommand(event: KeyboardEvent): ViewerCommand | null {
    if (event.ctrlKey || event.metaKey || event.altKey) return null;

    const pan = event.shiftKey ? PAN_KEYS[event.key] : undefined;
    if (pan) return { type: 'pan', dx: pan[0], dy: pan[1] };

    switch (event.key) {
        case '+': case '=': return { type: 'zoom-in' };
        case '-': case '_': return { type: 'zoom-out' };
        case '0': return { type: 'fit' };
        default: return null;
    }
}
