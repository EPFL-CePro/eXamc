import { postText } from "@examc/helpers/http";
import { LogModal } from "@examc/modals";


/**
 * Loads the AMC log file and shows it in its modal.
 *
 * @param {string} options.url - The URL returning the log file content.
 * @param {string} options.csrfToken - The CSRF token of the page.
 */
export async function openLogFile(options: { url: string; csrfToken: string }): Promise<void> {
    const { url, csrfToken } = options;
    const modalWrapper = new LogModal();

    modalWrapper.setTitle("AMC log file");

    try {
        modalWrapper.setOutput(await postText(url, { csrfmiddlewaretoken: csrfToken }));
    } catch (error) {
        console.error(error);
        modalWrapper.setOutput('The AMC log file could not be loaded.');
    }

    modalWrapper.show();
}

