/**
 * Globals the review page gets from <script> tags rather than imports: jQuery (with its
 * draggable and jquery-comments plugins), htmx, and MathJax's configuration object.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const $: any;

declare const htmx: {
    ajax(method: string, url: string, options: Record<string, unknown>): Promise<void>;
};

interface Window {
    MathJax?: unknown;

    // Called from inline handlers in the templates
    updatePagesGroupCheckBox?: (itemId: string, checked: boolean | null, adjustment: string | null, zero: boolean, full: boolean) => void;
    sendScheme?: (tab: HTMLButtonElement, event?: Event) => boolean;
    createMarker4CorrBox?: (left: number, top: number, width: number, height: number, persist?: boolean) => void;
    saveStudentReportNote?: (textarea: HTMLTextAreaElement) => void;
}
