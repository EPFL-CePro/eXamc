import { postText } from '@examc/helpers/http.ts';
import { ModuleUninitialized } from './errors.ts';
import { showInfo } from './info.ts';
import type { ResultsUrls } from './types.ts';

let urls: ResultsUrls | null = null;

/** Sets the API endpoints. Called by index.ts once the DOM has loaded. */
export function initResults(endpoints: ResultsUrls): void {
    urls = endpoints;
}

/**
 * Generates the results, then reloads the page to show them.
 */
export async function generateResults(): Promise<void> {
    if (!urls) throw new ModuleUninitialized('results.ts', 'initResults');

    try {
        await postText(urls.generate, {});
        window.location.reload();
    } catch (error) {
        console.error(error);
        showInfo('Failed to generate results.');
    }
}