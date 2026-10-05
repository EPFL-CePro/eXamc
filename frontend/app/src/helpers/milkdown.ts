import { Crepe } from '@milkdown/crepe';
import { parserCtx, serializerCtx } from '@milkdown/kit/core';
import { replaceAll } from '@milkdown/kit/utils';
import { markdown as markdownLanguage } from '@codemirror/lang-markdown';
import { EditorState } from '@codemirror/state';
import { EditorView } from '@codemirror/view';
import { basicSetup } from 'codemirror';
import katex from 'katex';

import { confirmDialog } from '@examc/helpers/confirm-dialog';

import '@milkdown/crepe/theme/common/style.css';
import '@milkdown/crepe/theme/frame.css';

// KaTeX API used by its extensions (mhchem...), not in its public types
const katexWithMacros = katex as typeof katex & { __defineMacro(name: string, body: string): void };

// Delay before checking again, while typing in the source, if the visual editor can take the text
const COMPATIBILITY_CHECK_DELAY_MS = 300;

const HELP_TEXT = {
    wysiwyg: 'Formatted text (bold, lists, titles) and simple formulas like $x^2$. Recommended.',
    source: 'For LaTeX users: Markdown and LaTeX typed directly, saved exactly as written, without any transformation.',
    locked: 'A text that the visual editor would change (LaTeX commands, advanced Markdown) can only be edited in Source.',
};


/**
 * Defines LaTeX macros (like those of the exam commands.tex) for all the math rendered by the editors.
 * Crepe renders inline math without KaTeX options: the macros have to be global.
 */
export function registerKatexMacros(macros: Record<string, string>): void {
    for (const [name, body] of Object.entries(macros)) {
        katexWithMacros.__defineMacro(name, body);
    }
}

export type MilkdownEditorMode = 'wysiwyg' | 'source';

interface InitMilkdownEditorOptions {
    target: HTMLElement;
    initialValue?: string;
    readonly?: boolean;
    // Forces the initial mode. By default, it is chosen by the user for an empty text, and from the text otherwise
    mode?: MilkdownEditorMode;
    // Initial mode of an empty text, instead of asking the user to choose
    emptyMode?: MilkdownEditorMode;
    onChange?: (markdown: string) => void;
}

export interface MilkdownEditor {
    getMarkdown(): string;
    getMode(): MilkdownEditorMode;
    setMode(mode: MilkdownEditorMode): void;
    destroy(): void;
}


// Math ($...$, $$...$$) and code spans, where LaTeX commands are rendered or kept by the visual editor
const MATH_OR_CODE_RE = /\$\$[\s\S]*?\$\$|(?<!\\)\$(?:\\.|[^$\\])+\$|`[^`]*`/g;
const LATEX_COMMAND_RE = /\\[A-Za-z@]/;

// LaTeX commands outside of the math (\centermath, \vspace...) are shown as raw text by the visual editor
function containsLatexOutsideMath(markdown: string): boolean {
    return LATEX_COMMAND_RE.test(markdown.replace(MATH_OR_CODE_RE, ''));
}

// Font Awesome icon (loaded by base.html)
function createIcon(name: string, className = ''): HTMLElement {
    const icon = createElement('i', `fa-solid fa-${name} ${className}`.trim());
    icon.setAttribute('aria-hidden', 'true');
    return icon;
}

function normalizeMarkdown(markdown: string): string {
    return markdown.replace(/\s+$/, '');
}

// eslint-disable-next-line no-undef
function createElement<K extends keyof HTMLElementTagNameMap>(
    tag: K, className: string, text?: string,
    // eslint-disable-next-line no-undef
): HTMLElementTagNameMap[K] {
    const element = document.createElement(tag);
    element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}


/**
 * Creates a markdown editor inside `target`, with two modes switched by a toggle above it:
 * - "wysiwyg": Milkdown Crepe
 * - "source": CodeMirror on the raw markdown, saved as typed, created on the first switch
 *
 * A text is never edited in both modes when Milkdown would change it: Milkdown parses and serializes the text,
 * if the result differs (LaTeX commands, advanced markdown...), or if the text contains LaTeX commands outside
 * of the math, that Milkdown would show as raw text, the text can only be edited in "source".
 * An empty text first shows a choice between the two modes, with their description, unless `emptyMode` is given.
 * Without edition in Milkdown, `getMarkdown()` returns the original text, not its serialization by Milkdown.
 */
export function initMilkdownEditor({
    target,
    initialValue = '',
    readonly = false,
    mode,
    emptyMode,
    onChange,
}: InitMilkdownEditorOptions): MilkdownEditor {
    const isEmpty = initialValue.trim() === '';
    const initialMode = mode ?? (isEmpty ? emptyMode : undefined);

    let lastMarkdown = initialValue;
    let currentMode: MilkdownEditorMode = 'source';
    // The mode is chosen once Crepe has checked the text, or by the user for an empty text
    let modeChosen = initialMode !== undefined;
    let ready = false;
    let failed = false;
    let destroyed = false;
    let visualCompatible = true;
    let compatibilityTimer: number | undefined;
    let sourceView: EditorView | null = null;
    // Text loaded in Crepe and its serialization: unchanged serialization means no edition in Crepe
    let visualBaseline: { source: string; serialized: string } | null = null;

    // Choice of the mode, for an empty text
    const chooser = createElement('div', 'milkdown-mode-chooser');
    chooser.append(createElement('div', 'milkdown-mode-chooser-title', 'Choose how to write this text:'));
    const chooserCards = createElement('div', 'milkdown-mode-chooser-cards');
    chooserCards.append(
        createChooserCard('eye', 'Visual editor', HELP_TEXT.wysiwyg, 'wysiwyg'),
        createChooserCard('code', 'Markdown / LaTeX source', HELP_TEXT.source, 'source'),
    );
    chooser.append(chooserCards);

    // Editor: toolbar, help, lock note and the two editors
    const shell = createElement('div', 'milkdown-editor-shell');

    const toolbar = createElement('div', 'milkdown-mode-toggle');
    const status = createElement('span', 'milkdown-mode-status');
    const helpButton = createElement('button', 'milkdown-mode-help-button');
    helpButton.type = 'button';
    helpButton.title = 'Which editor should I use?';
    helpButton.setAttribute('aria-label', helpButton.title);
    helpButton.append(createIcon('circle-info'));
    helpButton.setAttribute('aria-expanded', 'false');
    const statusGroup = createElement('div', 'milkdown-mode-status-group');
    statusGroup.append(status, helpButton);

    const buttonGroup = createElement('div', 'milkdown-mode-buttons');
    buttonGroup.setAttribute('role', 'group');
    const buttons: Record<MilkdownEditorMode, HTMLButtonElement> = {
        wysiwyg: createToggleButton('eye', 'Visual', 'wysiwyg'),
        source: createToggleButton('code', 'Source', 'source'),
    };
    // Shown on the Visual button when the text can only be edited in Source
    const visualLockIcon = createIcon('lock', 'milkdown-mode-lock-icon');
    buttons.wysiwyg.append(visualLockIcon);
    buttonGroup.append(buttons.wysiwyg, buttons.source);
    toolbar.append(statusGroup, buttonGroup);

    const help = createElement('div', 'milkdown-mode-help');
    help.hidden = true;
    for (const [title, text] of [
        ['Visual', HELP_TEXT.wysiwyg],
        ['Source', HELP_TEXT.source],
        ['', HELP_TEXT.locked],
    ] as const) {
        const line = createElement('div', '');
        if (title) line.append(createElement('strong', '', `${title}: `));
        line.append(text);
        help.append(line);
    }
    helpButton.addEventListener('click', () => {
        help.hidden = !help.hidden;
        helpButton.setAttribute('aria-expanded', String(!help.hidden));
    });

    const lockNote = createElement('div', 'milkdown-mode-lock-note');
    lockNote.append(
        createIcon('lock'),
        createElement('span', '', 'The visual editor would change this text (LaTeX commands, advanced Markdown): '
            + 'it can only be edited in Source.'),
    );
    const clearButton = createElement('button', 'milkdown-mode-clear-button');
    clearButton.type = 'button';
    clearButton.append(createIcon('eraser'), ' Clear and switch to visual');
    clearButton.addEventListener('click', () => void clearAndSwitchToVisual());
    lockNote.append(clearButton);

    const loading = createElement('div', 'milkdown-editor-loading text-muted', 'Loading the editor…');
    const wysiwygHost = createElement('div', 'milkdown-wysiwyg-host');
    const sourceHost = createElement('div', 'milkdown-source-host');

    shell.append(toolbar, help, lockNote, loading, wysiwygHost, sourceHost);
    target.append(chooser, shell);

    function createChooserCard(
        icon: string, title: string, text: string, cardMode: MilkdownEditorMode,
    ): HTMLButtonElement {
        const card = createElement('button', 'milkdown-mode-chooser-card');
        card.type = 'button';
        const cardTitle = createElement('strong', '');
        cardTitle.append(createIcon(icon), ` ${title}`);
        card.append(cardTitle, createElement('span', '', text));
        card.addEventListener('click', () => {
            modeChosen = true;
            setMode(cardMode);
            focus();
        });
        return card;
    }

    function createToggleButton(icon: string, label: string, buttonMode: MilkdownEditorMode): HTMLButtonElement {
        const button = createElement('button', 'milkdown-mode-button');
        button.type = 'button';
        button.append(createIcon(icon), ` ${label}`);
        button.addEventListener('click', () => {
            setMode(buttonMode);
            focus();
        });
        return button;
    }

    function focus(): void {
        if (currentMode === 'source') sourceView?.focus();
        else wysiwygHost.querySelector<HTMLElement>('.ProseMirror')?.focus();
    }

    function updateMarkdown(markdown: string): void {
        if (markdown === lastMarkdown) return;
        lastMarkdown = markdown;
        onChange?.(markdown);
    }

    const crepe = new Crepe({
        root: wysiwygHost,
        defaultValue: initialValue,
        features: {
            [Crepe.Feature.TopBar]: true,
            // Images would need an upload to the exam project: not supported yet
            [Crepe.Feature.ImageBlock]: false,
        },
    });

    crepe.setReadonly(readonly);
    crepe.on((listener) => {
        listener.markdownUpdated(() => {
            // Ignores the updates of the hidden editor (e.g. the reload of the source markdown)
            if (currentMode === 'wysiwyg' && !destroyed) updateMarkdown(getMarkdown());
        });
    });

    crepe.create()
        .then(() => {
            ready = true;
            if (destroyed) {
                void crepe.destroy();
                return;
            }

            visualBaseline = { source: initialValue, serialized: crepe.getMarkdown() };
            visualCompatible = isVisualCompatible(initialValue);

            if (!modeChosen && (!isEmpty || readonly)) {
                modeChosen = true;
                setMode(visualCompatible ? 'wysiwyg' : 'source');
            } else if (currentMode === 'wysiwyg' && lastMarkdown !== initialValue) {
                // Chosen before Crepe was ready
                loadInVisualEditor(lastMarkdown);
            } else {
                render();
            }
        })
        .catch((error: unknown) => {
            console.error('Milkdown editor creation failed', error);
            failed = true;
            modeChosen = true;
            visualCompatible = false;
            if (!destroyed) setMode('source');
        });

    // True when Milkdown keeps the text as it is (except trailing spaces) and can display it: it can be
    // edited in both modes
    function isVisualCompatible(markdown: string): boolean {
        if (markdown.trim() === '') return true;
        if (!ready || containsLatexOutsideMath(markdown)) return false;

        try {
            const serialized = crepe.editor.action((ctx) => ctx.get(serializerCtx)(ctx.get(parserCtx)(markdown)));
            return normalizeMarkdown(serialized) === normalizeMarkdown(markdown);
        } catch {
            return false;
        }
    }

    function loadInVisualEditor(markdown: string): void {
        crepe.editor.action(replaceAll(markdown));
        visualBaseline = { source: markdown, serialized: crepe.getMarkdown() };
    }

    function scheduleCompatibilityCheck(): void {
        window.clearTimeout(compatibilityTimer);
        compatibilityTimer = window.setTimeout(() => {
            if (destroyed || failed) return;
            visualCompatible = isVisualCompatible(getMarkdown());
            render();
        }, COMPATIBILITY_CHECK_DELAY_MS);
    }

    function createSourceView(): EditorView {
        return new EditorView({
            parent: sourceHost,
            state: EditorState.create({
                doc: lastMarkdown,
                extensions: [
                    basicSetup,
                    markdownLanguage(),
                    EditorView.lineWrapping,
                    EditorState.readOnly.of(readonly),
                    EditorView.editable.of(!readonly),
                    EditorView.updateListener.of((update) => {
                        if (!update.docChanged) return;
                        updateMarkdown(update.state.doc.toString());
                        scheduleCompatibilityCheck();
                    }),
                ],
            }),
        });
    }

    function setSourceText(markdown: string): void {
        if (!sourceView) {
            sourceView = createSourceView();
        } else if (sourceView.state.doc.toString() !== markdown) {
            sourceView.dispatch({ changes: { from: 0, to: sourceView.state.doc.length, insert: markdown } });
        }
    }

    function getMarkdown(): string {
        if (destroyed) return lastMarkdown;
        if (currentMode === 'source') return sourceView ? sourceView.state.doc.toString() : lastMarkdown;
        if (!ready) return lastMarkdown;

        const markdown = crepe.getMarkdown();
        // Not edited in Crepe: the text is kept as it was, not rewritten by Milkdown
        return visualBaseline && markdown === visualBaseline.serialized ? visualBaseline.source : markdown;
    }

    function setMode(newMode: MilkdownEditorMode): void {
        if (destroyed) return;

        if (newMode !== currentMode || (newMode === 'source' && !sourceView)) {
            const markdown = getMarkdown();

            if (newMode === 'source') {
                lastMarkdown = markdown;
                setSourceText(markdown);
            } else {
                window.clearTimeout(compatibilityTimer);
                visualCompatible = isVisualCompatible(markdown);
                // Blocked: Milkdown would change the text
                if (!visualCompatible && markdown.trim() !== '') {
                    render();
                    return;
                }
                lastMarkdown = markdown;
                if (ready) loadInVisualEditor(markdown);
            }

            currentMode = newMode;
        }

        render();
    }

    async function clearAndSwitchToVisual(): Promise<void> {
        if (readonly) return;

        const confirmed = await confirmDialog({
            title: 'Switch to the visual editor',
            warning: 'The current content of this text will be lost.',
            message: 'The visual editor cannot edit this text without changing it. '
                + 'Clear the text and start again in the visual editor?',
            confirmLabel: 'Yes, clear and switch',
            confirmClass: 'btn-danger',
        });
        if (!confirmed || destroyed) return;

        setSourceText('');
        updateMarkdown('');
        visualCompatible = true;
        setMode('wysiwyg');
    }

    function render(): void {
        const showChooser = !modeChosen && isEmpty && !readonly;
        const pending = !modeChosen && !showChooser;
        const visualBlocked = currentMode === 'source' && !visualCompatible && getMarkdown().trim() !== '';

        chooser.hidden = !showChooser;
        shell.hidden = showChooser;
        loading.hidden = !pending;
        wysiwygHost.hidden = pending || currentMode !== 'wysiwyg';
        sourceHost.hidden = pending || currentMode !== 'source';
        toolbar.hidden = pending;
        if (pending) help.hidden = true;

        status.textContent = currentMode === 'wysiwyg' ? 'Visual editor' : 'Source: saved as typed';
        lockNote.hidden = pending || !visualBlocked || failed;
        clearButton.hidden = readonly;

        buttons.wysiwyg.disabled = failed || visualBlocked;
        visualLockIcon.hidden = !buttons.wysiwyg.disabled;
        buttons.wysiwyg.title = failed
            ? 'The visual editor could not be loaded'
            : visualBlocked ? 'The visual editor would change this text' : '';

        for (const [buttonMode, button] of Object.entries(buttons)) {
            const active = buttonMode === currentMode;
            button.classList.toggle('active', active);
            button.setAttribute('aria-pressed', String(active));
        }
    }

    if (initialMode) setMode(initialMode);
    else render();

    return {
        getMarkdown,
        getMode: () => currentMode,
        setMode,
        destroy: () => {
            if (destroyed) return;
            lastMarkdown = getMarkdown();
            destroyed = true;
            window.clearTimeout(compatibilityTimer);
            sourceView?.destroy();
            if (ready) void crepe.destroy();
        },
    };
}
