import { isExamFinalized, Selectors } from "./config.ts";
import { showModal } from "./ajax.ts";

/** Disables the editing once the exam is finalized or locked. */
export function applyFinalizedReadOnlyState(container: Document | Element = document): void {
    if (!isExamFinalized()) return;

    // Disable inputs inside prep area only
    container.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(
        '#prep-first-page-panel input:not([type="hidden"]), #prep-first-page-panel textarea, #prep-first-page-panel select,' +
        '.sortable-section input:not([type="hidden"]), .sortable-section textarea, .sortable-section select,' +
        '.sortable-question input:not([type="hidden"]), .sortable-question textarea, .sortable-question select,' +
        '.sortable-answer input:not([type="hidden"]), .sortable-answer textarea, .sortable-answer select',
    ).forEach((el) => {
        if (el.closest("#unlockExamEditingForm")) return;
        el.disabled = true;
        el.classList.add("is-finalized-readonly");
    });

    // Markdown editors (already created read-only, see initMarkdownEditors)
    container.querySelectorAll("#prep-root .milkdown-editor-container").forEach((editorEl) => {
        editorEl.classList.add("finalized-editor-readonly");

        if (document.activeElement instanceof HTMLElement && editorEl.contains(document.activeElement)) {
            document.activeElement.blur();
        }

        editorEl.querySelectorAll('.ProseMirror, [contenteditable="true"]').forEach((el) => {
            el.setAttribute("contenteditable", "false");
            el.setAttribute("tabindex", "-1");
            el.classList.add("finalized-editor-surface");
        });
    });
}

export function openUnlockEditingModal(): void {
    showModal("#unlock_exam_editing_modal");
}

export function initUnlockEditing(): void {
    document.getElementById("confirmUnlockEditingBtn")?.addEventListener("click", () => {
        (document.getElementById("unlockExamEditingForm") as HTMLFormElement | null)?.submit();
    });
}

/** Clicks on a drag handle must not toggle the panel they are in. */
export function stopDragHandleClicks(): void {
    document.addEventListener("click", (event) => {
        if ((event.target as Element).closest(Selectors.dragHandle)) {
            event.stopPropagation();
        }
    });
}
