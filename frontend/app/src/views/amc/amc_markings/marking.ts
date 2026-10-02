import { byId } from '@examc/helpers/dom.ts';
import { getModal } from '@examc/helpers/modals.ts';
import { ModuleUninitialized } from './errors.ts';
import { state } from './state.ts';
import type { MarkingConfig } from './types.ts';

let config: MarkingConfig | null = null;

/** Sets the API endpoint. Called by index.ts once the DOM has loaded. */
export function initMarking(settings: MarkingConfig): void {
    config = settings;
}

/**
 * Appends a streamed response body to an element as it arrives.
 *
 * @param {Response} response - The streamed response.
 * @param {HTMLElement} target - The element receiving the text.
 */
async function streamInto(response: Response, target: HTMLElement): Promise<void> {
    if (!response.body) {
        target.textContent += await response.text();
        return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        target.textContent += decoder.decode(value, { stream: true });
        target.scrollTop = target.scrollHeight;
    }
    target.textContent += decoder.decode();
}

/** Runs AMC marking and shows its output live in the process modal. */
export async function runMarking(): Promise<void> {
    if (!config) throw new ModuleUninitialized('marking.ts', 'initMarking');
    if (state.markingRunning) return;

    byId('amc-process-modal-title').textContent = 'Marking';
    const output = byId('amc-process-modal-body');
    output.textContent = '';
    output.style.whiteSpace = 'pre-wrap';

    getModal({ type: 'local', element: byId('amc-process-modal') }).show();

    const body = new FormData();
    body.append('csrfmiddlewaretoken', config.csrfToken);
    body.append('update_scoring_strategy', String(byId<HTMLInputElement>('update-marking-scale').checked));

    state.markingRunning = true;
    try {
        // Plain fetch rather than postText: the output must be read while it streams.
        const response = await fetch(config.mark, { method: 'POST', body, credentials: 'same-origin' });
        if (!response.ok) throw new Error(`Marking request failed: ${response.status}`);

        await streamInto(response, output);
        output.textContent += '\n** MARKING COMPLETED! **';
        output.scrollTop = output.scrollHeight;
    } catch (error) {
        console.error(error);
        output.textContent = 'Error occurred';
    } finally {
        state.markingRunning = false;
    }
}