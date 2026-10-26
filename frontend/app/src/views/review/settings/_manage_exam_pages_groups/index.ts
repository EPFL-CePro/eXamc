import { openGradingHelp } from "./grading-help-modal";
import { showToasts } from "@examc/helpers/toasts.ts";
document.addEventListener("DOMContentLoaded", () => {
    const gradingHelpBtns = document.querySelectorAll<HTMLButtonElement>("[data-grading-help-group]");

    gradingHelpBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            openGradingHelp(btn).catch((error: unknown) => {
                console.error("Opening the grading help failed", error);
                showToast(error instanceof Error ? error.message : "Could not open the grading help.", { error: true });
            });
        });
    });
});
