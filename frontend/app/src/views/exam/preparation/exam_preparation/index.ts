import "./main.scss";

import { initActions } from "./actions.ts";
import { initFinalGeneration } from "./final-generation.ts";
import { initHtmx } from "./htmx.ts";
import { initMarkdownEditors, loadKatexMacros } from "./markdown-editors.ts";
import { stopPreviewPolling } from "./preview.ts";
import { initPreparationUI } from "./question-fields.ts";
import { applyFinalizedReadOnlyState, initUnlockEditing, stopDragHandleClicks } from "./read-only.ts";
import { initSavingOverlay } from "./saving-overlay.ts";
import { initScoringFormulas } from "./scoring-formulas.ts";
import { initAnswerSortable, initQuestionSortable, initSectionSortable } from "./sortable.ts";

initActions();
initFinalGeneration();
stopDragHandleClicks();
initHtmx();
initSavingOverlay();

// Native listener: the dialogs are Bootstrap 5 modals, whose events do not reliably reach
// jQuery handlers on this page (Bootstrap 4 is loaded too)
document.addEventListener("hidden.bs.modal", (event) => {
    if ((event.target as Element).id === "exam_preview_dialog") {
        stopPreviewPolling();
    }
});

document.addEventListener("DOMContentLoaded", () => {
    initSectionSortable();
    initQuestionSortable();
    initAnswerSortable();
    initScoringFormulas();
    initPreparationUI(document);
    loadKatexMacros();
    initMarkdownEditors(document);
    applyFinalizedReadOnlyState(document);
    initUnlockEditing();
});
