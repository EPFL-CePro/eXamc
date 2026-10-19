import { CSRF } from "./config.ts";
import { destroyMarkdownEditors, getEditorValues, initMarkdownEditors, syncMarkdownEditors } from "./markdown-editors.ts";
import { initPreparationUI } from "./question-fields.ts";
import { applyFinalizedReadOnlyState } from "./read-only.ts";
import { showSaveToast } from "./save-toast.ts";
import { initAnswerSortable, initQuestionSortable, initSectionSortable } from "./sortable.ts";

// The panels are saved with htmx: the markdown editors are synchronised before a request, destroyed before a swap
// and set up again after it.

export function initHtmx(): void {
    document.body.addEventListener("htmx:configRequest", (event) => {
        event.detail.headers["X-CSRFToken"] = CSRF;

        const form = event.detail.elt.closest("form");
        if (!form) return;

        getEditorValues(form).forEach(([textarea, value]) => {
            textarea.value = value;
            event.detail.parameters[textarea.name] = value;
        });
    });

    document.body.addEventListener("htmx:beforeRequest", (event) => {
        const form = event.detail.elt.closest("form");
        if (form) {
            syncMarkdownEditors(form);
        }
    });

    document.body.addEventListener("htmx:beforeSwap", (event) => {
        const { target, shouldSwap } = event.detail;
        // htmx does not swap error responses: keep the current editors alive
        if (!shouldSwap) return;

        destroyMarkdownEditors(target);
    });

    document.body.addEventListener("prepSaveFeedback", (event) => {
        if (event.detail && event.detail.saved) {
            showSaveToast("Saved", false);
        } else {
            showSaveToast("Not saved: please check the highlighted fields", true);
        }
    });

    document.body.addEventListener("htmx:responseError", (event) => {
        const { elt, requestConfig, xhr } = event.detail;
        if (!elt.closest("#prep-root")) return;
        if ((requestConfig.verb || "").toLowerCase() !== "post") return;

        showSaveToast(`Not saved: server error (${xhr.status})`, true);
    });

    document.body.addEventListener("htmx:afterSwap", (event) => {
        const target = event.target as Element;
        initSectionSortable();
        initQuestionSortable();
        initAnswerSortable();
        initPreparationUI(target);
        initMarkdownEditors(target);
        applyFinalizedReadOnlyState(target);
    });
}

