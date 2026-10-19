import { generateFinalExamFiles } from "./final-generation.ts";
import { openEditLaTeXFileDialog, openEditLaTeXPackagesDialog, saveEditedLaTeXFile, saveEditedLaTeXPackages } from "./latex.ts";
import { previewExam } from "./preview.ts";
import { openUnlockEditingModal } from "./read-only.ts";

/** The buttons of the templates (data-prep-action, and data-prep-arg when the action takes an argument). */
const ACTIONS: Record<string, (arg: string) => unknown> = {
    "preview": () => previewExam(),
    "generate-final": () => generateFinalExamFiles(),
    // "Generate anyway" of the dialog: the warnings are confirmed
    "generate-final-confirmed": () => generateFinalExamFiles(true),
    "edit-latex-file": (type) => openEditLaTeXFileDialog(type),
    "save-latex-file": () => saveEditedLaTeXFile(),
    "edit-latex-packages": (type) => openEditLaTeXPackagesDialog(type),
    "save-latex-packages": () => saveEditedLaTeXPackages(),
    "unlock-editing": () => openUnlockEditingModal(),
};

export function initActions(): void {
    document.addEventListener("click", (event) => {
        const button = (event.target as Element).closest<HTMLElement>("[data-prep-action]");
        const action = button?.dataset["prepAction"];
        if (!button || !action) return;

        const handler = ACTIONS[action];
        if (!handler) {
            console.error(`[preparation] Unknown action "${action}"`);
            return;
        }
        void handler(button.dataset["prepArg"] ?? "");
    });
}
