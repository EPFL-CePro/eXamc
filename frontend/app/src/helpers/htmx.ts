interface Htmx {
    process: (...args: unknown[]) => unknown;
    ajax: (...args: unknown[]) => unknown;
}

/**
 * Asserts that the htmx global is set and is an object
 * @param htmxGlobal
 * @throws {TypeError} if htmx is undefined, null, or not an object
 */
export function assertHtmx(htmxGlobal: unknown): asserts htmxGlobal is Htmx {
    if (
        htmxGlobal === undefined || htmxGlobal === null || typeof htmxGlobal !== "object" ||
        !("process" in htmxGlobal) || typeof htmxGlobal.process !== "function"
    ) {
        throw new TypeError("htmx is not defined or is not an object");
    }
}