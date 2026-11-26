/**
 * Globals the review page gets from <script> tags rather than imports: jQuery (with its
 * draggable and jquery-comments plugins), htmx, and MathJax's configuration object.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const $: any;

/** htmx doesn't have types, use `@examc/helpers/htmx.ts`' `assertHtmx` function to do some basic checks that it's correctly instanciated. */
declare const htmx: unknown;

interface Window {
    MathJax?: unknown;

    // Called from inline handlers in the templates
    updatePagesGroupCheckBox?: (itemId: string, checked: boolean | null, adjustment: string | null, zero: boolean, full: boolean) => void;
    sendScheme?: (tab: HTMLButtonElement, event?: Event) => boolean;
    createMarker4CorrBox?: (left: number, top: number, width: number, height: number, persist?: boolean) => void;
    saveStudentReportNote?: (textarea: HTMLTextAreaElement) => void;
}
