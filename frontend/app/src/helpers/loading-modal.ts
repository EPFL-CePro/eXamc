import { getPageBootstrap } from "@examc/helpers/page-bootstrap";

/**
 * Shows the spinner of base.html (#loadingModal) while `task` runs.
 * The modal has no fade: it can be hidden right after being shown.
 */
export async function withLoadingModal<T>(task: () => Promise<T>): Promise<T> {
    const element = document.getElementById("loadingModal");
    const modal = element ? getPageBootstrap().Modal.getOrCreateInstance(element, { backdrop: "static", keyboard: false }) : null;

    modal?.show();
    try {
        return await task();
    } finally {
        modal?.hide();
    }
}
