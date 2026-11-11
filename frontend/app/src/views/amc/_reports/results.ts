import { postJson } from '@examc/helpers/http.ts';

import { ModuleUninitialized } from './errors.ts';
import type { ResultsUrls } from './types.ts';

let urls: ResultsUrls | null = null;

/** Sets the API endpoints. Called by index.ts once the DOM has loaded. */
export function initResults(endpoints: ResultsUrls): void {
    urls = endpoints;
}

/**
 * Generates the results and statistics; the server then imports them in the background.
 *
 * @return {Promise<string>} The page to go to, following that import.
 * @throws {HttpError} If the generation fails (its body holds the `error`).
 */
export async function generateResults(): Promise<string> {
    if (!urls) throw new ModuleUninitialized('results.ts', 'initResults');
    const { redirect } = await postJson<{ redirect: string }>(urls.generate, {});
    return redirect;
}
