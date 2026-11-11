/**
 * Locks the AMC view while a job uses the project, like the import page does during an import:
 * every <fieldset data-amc-lock> is disabled (the server renders them disabled when the page loads
 * during a job), and #amc-job-banner (amc.html) says why.
 *
 * @param {boolean} locked - Lock or unlock.
 * @param {string} [reason] - Shown in the banner, e.g. "Corrected exams are being generated for this exam".
 */
export function lockAmcView(locked: boolean, reason?: string): void {
    const lockableElements = document.querySelectorAll<HTMLFieldSetElement|HTMLInputElement>('[data-amc-lock]');
    console.log(lockableElements);

    for (const lockableElement of lockableElements) {
        lockableElement.disabled = locked;
    }

    const banner = document.getElementById('amc-job-banner');
    if (!banner) return;
    banner.hidden = !locked;
    const reasonElement = banner.querySelector('[data-amc-lock-reason]');
    if (reason && reasonElement) reasonElement.textContent = reason;
}

/** Whether the AMC view is locked: for actions that aren't form controls (e.g. the scan viewer's boxes). */
export function isAmcViewLocked(): boolean {
    return document.querySelector('fieldset[data-amc-lock]:disabled') !== null;
}