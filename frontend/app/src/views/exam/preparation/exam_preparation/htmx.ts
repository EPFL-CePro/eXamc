import { CSRF } from "./config.ts";
import { destroyMarkdownEditors, getEditorValues, initMarkdownEditors, syncMarkdownEditors } from "./markdown-editors.ts";
import { initPreparationUI } from "./question-fields.ts";
import { applyFinalizedReadOnlyState } from "./read-only.ts";
import { showSaveToast } from "./save-toast.ts";
import { initAnswerSortable, initQuestionSortable, initSectionSortable } from "./sortable.ts";

// The panels are saved with htmx: the markdown editors are synchronised before a request, destroyed before a swap
// and set up again after it.

interface HtmxDetail {
    elt?: Element;
    target?: Element;
    shouldSwap?: boolean;
    headers: Record<string, string>;
    parameters: Record<string, string>;
    requestConfig?: { verb?: string };
    xhr: XMLHttpRequest;
}

type HtmxEvent = CustomEvent<HtmxDetail>;

export function initHtmx(): void {
    document.body.addEventListener("htmx:configRequest", (e) => {
        const event = e as HtmxEvent;
        if (CSRF) {
            event.detail.headers["X-CSRFToken"] = CSRF;
        }

        const form = event.detail.elt?.closest("form");
        if (!form) return;

        getEditorValues(form).forEach(([textarea, value]) => {
            textarea.value = value;
            event.detail.parameters[textarea.name] = value;
        });
    });

    document.body.addEventListener("htmx:beforeRequest", (e) => {
        const form = (e as HtmxEvent).detail.elt?.closest("form");
        if (form) {
            syncMarkdownEditors(form);
        }
    });

    document.body.addEventListener("htmx:beforeSwap", (e) => {
        const { target, shouldSwap } = (e as HtmxEvent).detail;
        // htmx does not swap error responses: keep the current editors alive
        if (!target || !shouldSwap) return;

        destroyMarkdownEditors(target);
    });

    document.body.addEventListener("prepSaveFeedback", (e) => {
        const detail = (e as CustomEvent<{ saved?: boolean } | null>).detail;
        if (detail && detail.saved) {
            showSaveToast("Saved", false);
        } else {
            showSaveToast("Not saved: please check the highlighted fields", true);
        }
    });

    document.body.addEventListener("htmx:responseError", (e) => {
        const { elt, requestConfig, xhr } = (e as HtmxEvent).detail;
        if (!elt || !elt.closest("#prep-root")) return;
        if ((requestConfig?.verb || "").toLowerCase() !== "post") return;

        showSaveToast(`Not saved: server error (${xhr.status})`, true);
    });

    document.body.addEventListener("htmx:afterSwap", (e) => {
        const target = e.target as Element;
        initSectionSortable();
        initQuestionSortable();
        initAnswerSortable();
        initPreparationUI(target);
        initMarkdownEditors(target);
        applyFinalizedReadOnlyState(target);
    });
}

