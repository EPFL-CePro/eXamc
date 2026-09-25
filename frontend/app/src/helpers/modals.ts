import { Modal } from "bootstrap";

/**
 * Retrieves or creates a Modal instance based on the provided options.
 * If the modal type is "loading", it attempts to find the loading modal element in the DOM.
 * Throws an error if the required element cannot be found or is not provided.
 *
 * @param {Object} options - Configuration options for retrieving the modal.
 * @param {"loading" | "local"} options.type - The type of modal to retrieve. "loading" will search for an element with the id 'loading-modal'.
 * @param {HTMLElement|null} [options.element] - The HTMLElement to use for creating the modal. If `type` is "loading", this is optional since the method will search for the 'loading-modal' element.
 * @returns {Modal} An instance of the Modal class associated with the specified element.
 * @throws {Error} If `type` is "loading" and no element with id 'loading-modal' is found.
 * @throws {Error} If no element is provided or found to create the modal.
 */
export function getModal(options: { type: "loading" | "local", element?: HTMLElement | null }): Modal {
    const { type } = options;
    let { element } = options;

    if (type == "loading") {
        // tries to find the loading modal element, throw an error if it's not found
        element = document.getElementById('loading-modal');
        if (!element) throw new Error("Couldn't find loading modal. Is an element with id 'loading-modal' present on the page?");
    }

    // the element is required, throw an error if it's not provided
    if (!element) throw new Error("No element found/passed to create new Modal.");

    return new Modal(element);
}