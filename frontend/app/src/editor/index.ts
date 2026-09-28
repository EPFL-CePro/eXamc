import { Crepe, type CrepeConfig } from '@milkdown/crepe';
import { getHTML, getMarkdown } from '@milkdown/kit/utils'

import '@milkdown/crepe/theme/common/style.css';
import '@milkdown/crepe/theme/frame.css';

import "./style.scss";

const editors = new WeakMap<HTMLElement, Promise<Crepe>>();

const DEFAULT_EDITOR_OPTIONS: CrepeConfig = {
    features: {
        [Crepe.Feature.BlockEdit]: false,  // no drag handle, "+" button or slash menu
        [Crepe.Feature.ImageBlock]: false,
        [Crepe.Feature.TopBar]: true,
    }
};


/**
 * Initializes a Crepe editor on the specified target element with the provided options.
 *
 * @param {Object} options - Configuration options for editor initialization.
 * @param {HTMLElement} options.target - The DOM element where the editor will be initialized.
 * @param {string} [options.defaultValue] - The optional default value to populate the editor with.
 *
 * @return {Promise<Crepe>} A promise that resolves with the initialized Crepe editor instance.
 */
export async function initEditor(
    options: {
        target: HTMLElement;
        defaultValue?: string;
    }
): Promise<Crepe> {
    const { target, defaultValue } = options;

    // Already initialized (or currently initializing) on this element: reuse it
    const existing = editors.get(target);
    if (existing) return existing;

    const crepe = new Crepe({
        ...DEFAULT_EDITOR_OPTIONS,
        root: target,
        defaultValue: defaultValue ?? '',
    });

    const ready = crepe.create().then(() => crepe);
    editors.set(target, ready);

    // If creation fails, forget it so a retry is possible
    ready.catch(() => editors.delete(target));

    return ready;
}


/**
 * Retrieves the value from the editor in the specified format.
 *
 * @param {Object} options - Options to configure the value retrieval.
 * @param {Crepe} options.editor - The editor instance to retrieve the value from.
 * @param {"html" | "markdown"} [options.format="html"] - The format in which to return the value. Defaults to "html".
 * @return {string} The value of the editor content in the specified format.
 */
export function getEditorContent(
    options: {
        editor: Crepe
        format?: "html" | "markdown"
    }
) {
    const { editor, format = "html" } = options;

    switch (format) {
        case "html": return editor.editor.action(getHTML());
        case "markdown": return editor.editor.action(getMarkdown());
    }
}
