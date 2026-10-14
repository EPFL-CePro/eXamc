import { markdown } from '@codemirror/lang-markdown';
import { StreamLanguage } from '@codemirror/language';
import { stex } from '@codemirror/legacy-modes/mode/stex';
import { Compartment, type Extension } from '@codemirror/state';
import { oneDark } from '@codemirror/theme-one-dark';
import { indentWithTab } from '@codemirror/commands';
import { EditorView, keymap } from '@codemirror/view';
import { githubDark, githubLight } from '@uiw/codemirror-theme-github';
import { basicSetup } from 'codemirror';

import { BaseEditor } from './base.ts';
import { getCodeFontFamily } from '@examc/helpers/fonts.ts';

/** A choice offered to the user: its label, and the CodeMirror extension it enables. */
interface CodeChoice {
    label: string;
    extension: () => Extension;
}

/** Languages the code editor can highlight. */
export type CodeLanguage = 'latex' | 'markdown' | 'plain';

export const CODE_LANGUAGES: Record<CodeLanguage, CodeChoice> = {
    latex: { label: 'LaTeX', extension: () => StreamLanguage.define(stex) },
    markdown: { label: 'Markdown', extension: () => markdown() },
    plain: { label: 'Plain text', extension: () => [] },
};

/** Color themes of the code editor. */
export type CodeTheme = 'default' | 'github-light' | 'github-dark' | 'one-dark';

export const CODE_THEMES: Record<CodeTheme, CodeChoice> = {
    'default': { label: 'Default', extension: () => [] },
    'github-light': { label: 'GitHub light', extension: () => githubLight },
    'github-dark': { label: 'GitHub dark', extension: () => githubDark },
    'one-dark': { label: 'One Dark', extension: () => oneDark },
};

export function isCodeLanguage(value: string): value is CodeLanguage {
    return value in CODE_LANGUAGES;
}

export function isCodeTheme(value: string): value is CodeTheme {
    return value in CODE_THEMES;
}

function wrappingExtension(enabled: boolean): Extension {
    return enabled ? EditorView.lineWrapping : [];
}

export interface CodeEditorOptions {
    /** The element the editor is created in. */
    target: HTMLElement;
    /** The initial content. */
    defaultValue?: string;
    /** The highlighted language. Defaults to plain text. */
    language?: CodeLanguage;
    /** The color theme. Defaults to the default (light) theme. */
    theme?: CodeTheme;
    /** Whether long lines wrap. Defaults to true. */
    lineWrapping?: boolean;
    /** Id of the element labelling the editor, for screen readers. */
    labelledBy?: string;
    /** CSS height of the editor; its content scrolls inside. Defaults to 60vh. */
    height?: string;
}

interface Slots {
    language: Compartment;
    theme: Compartment;
    wrapping: Compartment;
}

interface Settings {
    language: CodeLanguage;
    theme: CodeTheme;
    lineWrapping: boolean;
}

/** A code editor (CodeMirror), with line numbers and syntax highlighting. */
export class CodeEditor extends BaseEditor {
    /** Parts of the configuration that can be swapped after creation. */
    private readonly slots: Slots;
    private readonly settings: Settings;

    private constructor(target: HTMLElement, public readonly view: EditorView, slots: Slots, settings: Settings) {
        super(target);
        this.slots = slots;
        this.settings = { ...settings };
    }

    /**
     * Creates a code editor on an element, or returns the one it already has.
     * CodeMirror is created synchronously; the promise keeps the same API as the other editors.
     *
     * @param {CodeEditorOptions} options - The editor's options.
     * @return {Promise<CodeEditor>} The editor.
     */
    public static create({
        target,
        defaultValue = '',
        language = 'plain',
        theme = 'default',
        lineWrapping = true,
        labelledBy,
        height = '60vh',
    }: CodeEditorOptions): Promise<CodeEditor> {
        return BaseEditor.attach(target, () => {
            const slots: Slots = { language: new Compartment(), theme: new Compartment(), wrapping: new Compartment() };

            const view = new EditorView({
                parent: target,
                doc: defaultValue,
                extensions: [
                    basicSetup,
                    // Tab / Shift+Tab indent and outdent instead of moving the focus
                    keymap.of([indentWithTab]),
                    // Escape stays in the editor: it closes CodeMirror's panels and, followed
                    // by Tab, moves the focus out, instead of closing the surrounding dialog
                    EditorView.domEventHandlers({
                        keydown: (event) => {
                            if (event.key === 'Escape') event.stopPropagation();
                            return false; // CodeMirror still handles the key
                        },
                    }),
                    slots.theme.of(CODE_THEMES[theme].extension()),
                    slots.language.of(CODE_LANGUAGES[language].extension()),
                    slots.wrapping.of(wrappingExtension(lineWrapping)),
                    EditorView.theme({
                        '&': { height, border: '1px solid var(--bs-border-color, #dee2e6)', borderRadius: '0.375rem' },
                        '.cm-scroller': {
                            overflow: 'auto',
                            fontFamily: getCodeFontFamily(),
                            fontWeight: 200,
                            fontSize: '.9rem',
                            lineHeight: '1.5',
                        },
                    }),
                    labelledBy ? EditorView.contentAttributes.of({ 'aria-labelledby': labelledBy }) : [],
                ],
            });

            return Promise.resolve(new CodeEditor(target, view, slots, { language, theme, lineWrapping }));
        });
    }

    public get language(): CodeLanguage {
        return this.settings.language;
    }

    public get theme(): CodeTheme {
        return this.settings.theme;
    }

    public get lineWrapping(): boolean {
        return this.settings.lineWrapping;
    }

    /** Changes the highlighted language, keeping the content and the undo history. */
    public setLanguage(language: CodeLanguage): void {
        if (language === this.settings.language) return;
        this.settings.language = language;
        this.view.dispatch({ effects: this.slots.language.reconfigure(CODE_LANGUAGES[language].extension()) });
    }

    /** Changes the color theme. */
    public setTheme(theme: CodeTheme): void {
        if (theme === this.settings.theme) return;
        this.settings.theme = theme;
        this.view.dispatch({ effects: this.slots.theme.reconfigure(CODE_THEMES[theme].extension()) });
    }

    /** Turns the wrapping of long lines on or off. */
    public setLineWrapping(enabled: boolean): void {
        if (enabled === this.settings.lineWrapping) return;
        this.settings.lineWrapping = enabled;
        this.view.dispatch({ effects: this.slots.wrapping.reconfigure(wrappingExtension(enabled)) });
    }

    public getContent(): string {
        return this.view.state.doc.toString();
    }

    public setContent(content: string): void {
        this.view.dispatch({ changes: { from: 0, to: this.view.state.doc.length, insert: content } });
    }

    public focus(): void {
        this.view.focus();
    }

    /** Measures the editor again; needed once it becomes visible, if it was created hidden. */
    public refresh(): void {
        this.view.requestMeasure();
    }

    protected dispose(): void {
        this.view.destroy();
    }
}