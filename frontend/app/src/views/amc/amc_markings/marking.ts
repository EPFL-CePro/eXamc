import { byId } from '@examc/helpers/dom.ts';
import { state } from './state.ts';
import { LogModal } from '@examc/modals/log.ts';
import { readTextStream } from '@examc/helpers/http.ts';


/** Runs AMC marking and shows its output live in the process modal. */
export async function runMarking(options: { csrfToken: string; mark: string }): Promise<void> {
    const { csrfToken, mark } = options;

    if (state.markingRunning) return;

    const logModal = new LogModal();
    logModal.setTitle('Marking');
    logModal.show();

    const body = new FormData();
    body.append('csrfmiddlewaretoken', csrfToken);
    body.append('update_scoring_strategy', String(byId<HTMLInputElement>('update-marking-scale').checked));

    state.markingRunning = true;

    try {
        // Plain fetch rather than postText: the output must be read while it streams.
        const response = await fetch(mark, { method: 'POST', body, credentials: 'same-origin' });
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