/**
 * Reads a response body as text, passing each chunk on as it arrives.
 * Without a readable body, the whole text is passed at once.
 *
 * @param {Response} response - The response to read.
 * @param {(text: string) => void} onText - Called with each decoded chunk.
 */
export async function readTextStream(response: Response, onText: (text: string) => void): Promise<void> {
    if (!response.body) {
        onText(await response.text());
        return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        onText(decoder.decode(value, { stream: true }));
    }

    // Flushes a multi-byte character split across the last chunks
    const rest = decoder.decode();
    if (rest) onText(rest);
}