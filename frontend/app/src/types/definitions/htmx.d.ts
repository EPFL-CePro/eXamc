export {};

/** What htmx puts in `event.detail`: only the fields the pages use. */
interface HtmxDetail {
    elt: Element;
    target: Element;
    xhr: XMLHttpRequest;
    requestConfig: { verb: string };
    /** htmx:beforeSwap: false for the error responses, that htmx does not swap. */
    shouldSwap: boolean;
    /** htmx:configRequest: the headers and parameters of the request, that the listener may change. */
    headers: Record<string, string>;
    parameters: Record<string, string>;
}

declare global {
    /** htmx, loaded by a <script> of base.html (CDN). */
    const htmx: {
        /** Sets up the hx-* attributes of HTML inserted by a script. */
        process(element: Element): void;
    };

    interface HTMLElementEventMap {
        "htmx:configRequest": CustomEvent<HtmxDetail>;
        "htmx:beforeRequest": CustomEvent<HtmxDetail>;
        "htmx:afterRequest": CustomEvent<HtmxDetail>;
        "htmx:beforeSwap": CustomEvent<HtmxDetail>;
        "htmx:afterSwap": CustomEvent<HtmxDetail>;
        "htmx:responseError": CustomEvent<HtmxDetail>;
        /** HX-Trigger of the panel views of the preparation page, after a POST. */
        "prepSaveFeedback": CustomEvent<{ saved?: boolean } | null>;
    }
}
