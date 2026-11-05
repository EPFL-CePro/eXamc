import { ensureOk } from "./errors";

/**
 * The file name a response gives in its Content-Disposition header, if any
 * (filename*=UTF-8''… first, as it holds non-ASCII names, then filename="…").
 */
function attachmentFileName(response: Response): string | null {
    const header = response.headers.get('Content-Disposition') ?? '';
    const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header)?.[1];
    if (encoded) return decodeURIComponent(encoded);
    return /filename="?([^";]+)"?/i.exec(header)?.[1] ?? null;
}

/**
 * Downloads a file: fetches it, then has the browser save it under the server's file name.
 *
 * @param {string} url - The file's URL.
 * @param {string} fallbackName - The name to use if the server gives none.
 * @throws {HttpError} If the response status is not OK.
 */
export async function downloadFile(url: string, fallbackName: string): Promise<void> {
    const response = await ensureOk(await fetch(url, { credentials: 'same-origin' }), url);

    const objectUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = attachmentFileName(response) ?? fallbackName;
    link.click();
    // Freed once the browser has started saving the file
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

