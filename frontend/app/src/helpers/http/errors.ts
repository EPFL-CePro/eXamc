/** A non-2xx response, keeping the body so callers can show the server's message. */
export class HttpError extends Error {
    constructor(
        readonly status: number,
        readonly url: string,
        readonly body: string,
    ) {
        super(`HTTP ${status} on ${url}`);
        this.name = 'HttpError';
    }
}

/**
 * Throws an HttpError, with the response's body, unless its status is OK.
 *
 * @param {Response} response - The response to check.
 * @param {string} url - The URL it came from, kept in the error.
 * @return {Promise<Response>} The same response, once checked.
 * @throws {HttpError} If the response status is not OK.
 */
export async function ensureOk(response: Response, url: string): Promise<Response> {
    if (!response.ok) throw new HttpError(response.status, url, await response.text());
    return response;
}

/** A failed request: the status (0 when the server was not reached), and what the server answered. */
export interface RequestFailure {
    status: number;
    text: string;
    json: unknown;
}

/**
 * Describes why a request failed.
 *
 * @param {unknown} error - What the request threw: an HttpError when the server answered with an error.
 * @return {RequestFailure} The status (0 when the server was not reached), the answer as text and as JSON if it is.
 */
export function describeFailure(error: unknown): RequestFailure {
    if (!(error instanceof HttpError)) {
        return { status: 0, text: error instanceof Error ? error.message : String(error), json: undefined };
    }

    let json: unknown;
    try {
        json = JSON.parse(error.body);
    } catch {
        json = undefined;
    }
    return { status: error.status, text: error.body, json };
}

/** The JSON body of a failed request, or an empty object. */
export function failureJson<T extends object>(failure: RequestFailure): Partial<T> {
    return (failure.json ?? {}) as Partial<T>;
}