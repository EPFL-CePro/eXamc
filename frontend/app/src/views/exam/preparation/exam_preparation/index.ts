import "./preparation.css";

import { initFinalGeneration, generateFinalExamFiles } from "./final-generation.ts";
import { initHtmx } from "./htmx.ts";
import { openEditLaTeXFileDialog, openEditLaTeXPackagesDialog, saveEditedLaTeXFile, saveEditedLaTeXPackages } from "./latex.ts";
import { initMarkdownEditors, loadKatexMacros } from "./markdown-editors.ts";
import { previewExam, stopPreviewPolling } from "./preview.ts";
import { initPreparationUI } from "./question-fields.ts";
import { applyFinalizedReadOnlyState, initUnlockEditing, openUnlockEditingModal, stopDragHandleClicks } from "./read-only.ts";
import { initScoringFormulas } from "./scoring-formulas.ts";
import { initAnswerSortable, initQuestionSortable, initSectionSortable } from "./sortable.ts";

// Called by the onclick attributes of the templates
window.previewExam = previewExam;
window.openEditLaTeXFileDialog = openEditLaTeXFileDialog;
window.saveEditedLaTeXFile = saveEditedLaTeXFile;
window.openEditLaTeXPackagesDialog = openEditLaTeXPackagesDialog;
window.saveEditedLaTeXPackages = saveEditedLaTeXPackages;
window.generateFinalExamFiles = generateFinalExamFiles;
window.openUnlockEditingModal = openUnlockEditingModal;

initFinalGeneration();
stopDragHandleClicks();
initHtmx();

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
