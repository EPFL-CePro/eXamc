import { Modal } from "bootstrap";

// store the initialized modals
const modals = new WeakMap<HTMLElement, Modal>();


/**
 * Retrieves or creates a Modal instance based on the provided options.
 * If the modal type is "loading", it attempts to find the loading modal element in the DOM.
 * Throws an error if the required element cannot be found or is not provided.
 *
 * @param {Object} options - Configuration options for retrieving the modal.
 * @param {"loading" | "local"} options.type - The type of modal to retrieve. "loading" will search for an element with the id 'loadingModal'.
 * @param {HTMLElement|null} [options.element] - The HTMLElement to use for creating the modal. If `type` is "loading", this is optional since the method will search for the 'loadingModal' element.
 * @returns {Modal} An instance of the Modal class associated with the specified element.
 * @throws {Error} If `type` is "loading" and no element with id 'loadingModal' is found.
 * @throws {Error} If no element is provided or found to create the modal.
 */
export function getModal(
    options: {
        type: "loading" | "local";
        element?: HTMLElement | null;
        modalOptions?: Partial<Modal.Options>;
    }
): Modal {
    const { type, modalOptions } = options;
    let { element } = options;

    if (type == "loading") {
        // tries to find the loading modal element, throw an error if it's not found
        element = document.getElementById('loadingModal');
        if (!element) throw new Error("Couldn't find loading modal. Is an element with id 'loadingModal' present on the page?");
    }

    // the element is required, throw an error if it's not provided
    if (!element) throw new Error("No element found/passed to create new Modal.");

    // try to retrieve the existing modal from the map
    const existingModal = modals.get(element);
    if (existingModal) return existingModal;

    // if not yet initialized, return a new Modal
    return new Modal(element, modalOptions);
}

/**
 * Runs a task while the loading modal is shown.
 * Bootstrap ignores hide() while a modal is still fading in, so the modal is hidden
 * only once it is fully shown; otherwise a fast task would leave it stuck open.
 *
 * @param {() => Promise<T>} task - The task to run.
 * @returns {Promise<T>} The task's result.
 */
export async function withLoading<T>(task: () => Promise<T>): Promise<T> {
    const modal = getModal({ type: "loading" });
    const element = document.querySelector<HTMLElement>('#loadingModal');
    if (!element) throw new Error("#loadingModal couldn't be found !");
 
    // Already open (e.g. nested call): don't wait for a 'shown' event that won't come.
    const shown = element.classList.contains('show')
        ? Promise.resolve()
        : new Promise<void>((resolve) => element.addEventListener('shown.bs.modal', () => resolve(), { once: true }));
 
    modal.show();
    try {
        return await task();
    } finally {
        await shown;
        modal.hide();
    }
}
