import { initAdvancedEditor, registerKatexMacros } from "@examc/editors";
import type { AdvancedEditor } from "@examc/types/editors";

import { isExamFinalized } from "./config.ts";

interface MarkdownEditorInstance {
    id: string;
    editor: AdvancedEditor;
    container: HTMLElement;
}

interface FieldSettings {
    suffix?: string;
    minHeight?: string;
    emptyMode?: "wysiwyg" | "source";
}

const markdownEditors = new Map<HTMLTextAreaElement, MarkdownEditorInstance>();
let markdownEditorSeq = 0;

// Editor settings by field (name suffix: the formsets prefix the names). The long texts ask the
// user to choose the editor mode when empty, the short ones start in the visual editor.
const MARKDOWN_FIELD_SETTINGS: FieldSettings[] = [
    { suffix: "first_page_text", minHeight: "200px" },
    { suffix: "question_text", minHeight: "160px" },
    { suffix: "section_text", minHeight: "100px", emptyMode: "wysiwyg" },
    { suffix: "answer_text", minHeight: "60px", emptyMode: "wysiwyg" },
];

function collectMarkdownTextareas(root: Document | Element | null = document): HTMLTextAreaElement[] {
    if (!root) return [];

    const textareas: HTMLTextAreaElement[] = [];

    if (root instanceof Element && root.matches("textarea.markdown-editor")) {
        textareas.push(root as HTMLTextAreaElement);
    }

    textareas.push(...root.querySelectorAll<HTMLTextAreaElement>("textarea.markdown-editor"));

    return textareas;
}

function syncTextarea(textarea: HTMLTextAreaElement): void {
    const instance = markdownEditors.get(textarea);
    if (!instance) return;

    textarea.value = instance.editor.getMarkdown();
}

export function syncMarkdownEditors(rootOrForm: Document | Element = document): void {
    collectMarkdownTextareas(rootOrForm).forEach(syncTextarea);
}

/** The textareas of `root` that have an editor, with the markdown of their editor. */
export function getEditorValues(root: Document | Element): [HTMLTextAreaElement, string][] {
    const values: [HTMLTextAreaElement, string][] = [];
    collectMarkdownTextareas(root).forEach((textarea) => {
        const instance = markdownEditors.get(textarea);
        if (instance) values.push([textarea, instance.editor.getMarkdown()]);
    });
    return values;
}

export function destroyMarkdownEditors(root: Document | Element = document): void {
    collectMarkdownTextareas(root).forEach((textarea) => {
        const instance = markdownEditors.get(textarea);
        if (!instance) return;

        syncTextarea(textarea);
        instance.editor.destroy();

        if (instance.container.parentNode) {
            instance.container.remove();
        }

        textarea.style.display = "";
        markdownEditors.delete(textarea);
        delete textarea.dataset["markdownEditorId"];
    });
}

function getMarkdownFieldSettings(textarea: HTMLTextAreaElement): FieldSettings {
    const name = textarea.name || "";
    return MARKDOWN_FIELD_SETTINGS.find((settings) => settings.suffix && name.endsWith(settings.suffix)) ?? {};
}

// Macros of the exam commands.tex, for the math preview (see get_exam_katex_macros)
export function loadKatexMacros(): void {
    const el = document.getElementById("prep-katex-macros");
    if (!el) return;

    try {
        registerKatexMacros(JSON.parse(el.textContent || "{}"));
    } catch (e) {
        console.error("Invalid KaTeX macros", e);
    }
}

export function initMarkdownEditors(root: Document | Element = document): void {
    collectMarkdownTextareas(root).forEach((textarea) => {
        if (markdownEditors.has(textarea)) {
            return;
        }

        const settings = getMarkdownFieldSettings(textarea);
        const container = document.createElement("div");
        container.className = "milkdown-editor-container mb-3";
        if (settings.minHeight) {
            container.style.setProperty("--prep-editor-min-height", settings.minHeight);
        }

        textarea.parentNode?.insertBefore(container, textarea.nextSibling);
        textarea.style.display = "none";

        const editor = initAdvancedEditor({
            target: container,
            initialValue: textarea.value || "",
            readonly: isExamFinalized(),
            ...(settings.emptyMode ? { emptyMode: settings.emptyMode } : {}),
            onChange: (markdown: string) => {
                textarea.value = markdown;
            },
        });

        const instance: MarkdownEditorInstance = {
            id: `md-${++markdownEditorSeq}`,
            editor,
            container,
        };

        markdownEditors.set(textarea, instance);
        textarea.dataset["markdownEditorId"] = instance.id;
    });
}
