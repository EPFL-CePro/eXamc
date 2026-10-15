import { byId } from '@examc/helpers/dom.ts';
import { ModuleUninitialized } from './errors.ts';
import { state } from './state.ts';
import type { MarkingConfig } from './types.ts';
import { LogModal } from '@examc/modals/log.ts';
import { readTextStream } from '@examc/helpers/http.ts';

let config: MarkingConfig | null = null;

/** Sets the API endpoint. Called by index.ts once the DOM has loaded. */
export function initMarking(settings: MarkingConfig): void {
    config = settings;
}

/** Runs AMC marking and shows its output live in the process modal. */
export async function runMarking(): Promise<void> {
    if (!config) throw new ModuleUninitialized('marking.ts', 'initMarking');
    if (state.markingRunning) return;

    const logModal = new LogModal();
    logModal.setTitle('Marking');
    logModal.show();

    const body = new FormData();
    body.append('csrfmiddlewaretoken', config.csrfToken);
    body.append('update_scoring_strategy', String(byId<HTMLInputElement>('update-marking-scale').checked));

    state.markingRunning = true;

    try {
        // Plain fetch rather than postText: the output must be read while it streams.
        const response = await fetch(config.mark, { method: 'POST', body, credentials: 'same-origin' });
        if (!response.ok) throw new Error(`Marking request failed: ${response.status}`);

        await readTextStream(response, (text) => logModal.appendToOutput(text));
        logModal.appendToOutput('\n** MARKING COMPLETED! **');
    } catch (error) {
        console.error(error);
        logModal.appendToOutput('\n** ERROR OCCURED! **');
        if (typeof error === "string") logModal.appendToOutput(error);
    } finally {
        state.markingRunning = false;
    }
}