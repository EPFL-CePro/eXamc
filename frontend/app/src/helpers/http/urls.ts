/**
 * Turns an AMC scan file path into the URL it is served from.
 *
 * @param {string} path - The scan path.
 * @return {string} The scan URL.
 */
export function toScanUrl(path: string): string {
    const parts = path.split('/');
    return `/${parts[1] ?? ''}/${parts[3] ?? ''}`;
}