/** A one-time Black Friday gag: an image over the page until it's clicked once. */
import blackFridayImage from './black-friday.webp';

const STORAGE_KEY = 'black-friday-popup-close';

function alreadyClosed(): boolean {
    try {
        return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
        return false; // storage blocked (private mode…): show it, it just won't be remembered
    }
}

function rememberClosed(): void {
    try {
        localStorage.setItem(STORAGE_KEY, 'true');
    } catch {
        // storage blocked: nothing to remember it with
    }
}

/**
 * Shows the popup once its image has loaded, unless it was already closed in this browser.
 * Only pages behind the login load this script, so the user is logged in.
 */
export function initBlackFridayPopup(): void {
    if (alreadyClosed()) return;

    const overlay = document.createElement('div');
    overlay.className = 'position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center p-3';
    overlay.style.cssText = 'z-index: 2000; background: rgb(0 0 0 / 0.75); cursor: pointer;';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Black Friday (click anywhere to close)');
    overlay.tabIndex = -1;

    const image = new Image();
    image.alt = 'Black Friday';
    image.className = 'img-fluid rounded shadow';
    image.style.maxHeight = '90vh';
    overlay.append(image);

    const close = (): void => {
        overlay.remove();
        document.removeEventListener('keydown', onKey);
        rememberClosed();
    };
    const onKey = (event: KeyboardEvent): void => {
        if (event.key === 'Escape') close();
    };

    overlay.addEventListener('click', close);
    // Shown once the image is there: no empty dark screen while it loads
    image.addEventListener('load', () => {
        document.body.append(overlay);
        document.addEventListener('keydown', onKey);
        overlay.focus();
    }, { once: true });
    image.src = blackFridayImage;
}