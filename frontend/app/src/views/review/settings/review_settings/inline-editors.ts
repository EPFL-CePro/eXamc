import { SimpleEditor } from "@examc/editors/simple";

/** The editor attached to each textarea, to sync its content before submitting. */
const editors = new WeakMap<HTMLTextAreaElement, SimpleEditor>();

/** Replaces each textarea in `root` with a simple editor; the hidden textarea keeps the content in HTML. */
export function attachGradingSchemePagesGroupEditors(elements: NodeListOf<HTMLTextAreaElement>): void {
    for (const textarea of elements) {
        // Skips textareas already handled, and hidden templates (such as a formset's empty form).
        if (textarea.dataset.editorAttached || textarea.parentElement?.closest("[hidden]")) continue;
        textarea.dataset.editorAttached = "true";

        const target = document.createElement("div");
        target.className = "border rounded";
        textarea.after(target);
        textarea.hidden = true;

        void SimpleEditor.create({
            target,
            defaultValue: textarea.value,
            format: "html",
            onChange: (content) => {
                textarea.value = content;
            },
        }).then((editor) => editors.set(textarea, editor));
    }
}

/** Copies the editors' current content into their textareas, bypassing the change callback's debounce. */
export function syncGradingSchemePagesGroupEditors(root: ParentNode): void {
    for (const textarea of root.querySelectorAll<HTMLTextAreaElement>("textarea")) {
        const editor = editors.get(textarea);
        if (editor) textarea.value = editor.getContent();
    }
}