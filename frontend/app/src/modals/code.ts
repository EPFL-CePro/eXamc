import '@awesome.me/webawesome/dist/styles/themes/default.css';
import '@awesome.me/webawesome/dist/components/tree/tree.js';
import '@awesome.me/webawesome/dist/components/tree-item/tree-item.js';

import {
    CODE_FONT_FAMILY,
    CODE_LANGUAGES,
    CODE_THEMES,
    CodeEditor,
    type CodeLanguage,
    type CodeTheme,
    isCodeLanguage,
    isCodeTheme,
} from '@examc/editors';
import { ExamcModal } from '@examc/modals/base.ts';

/** A file shown in the browser. */
export interface CodeFile {
    name: string;
    /** Passed to loadFile and saveFile. */
    path: string;
}

/** A folder shown in the browser, with its subfolders and files. */
export interface CodeFolder {
    name: string;
    folders?: CodeFolder[];
    files?: CodeFile[];
}

interface CommonOptions {
    title: string;
    /** The highlighted language. Defaults to plain text. */
    language?: CodeLanguage;
}

/** Edits one text: open(content), and Save closes the dialog once onSave resolves. */
export interface SingleFileOptions extends CommonOptions {
    /** Label shown above the editor, e.g. the file's path. */
    label: string;
    /** Saves the content. If it throws, the dialog stays open so the changes aren't lost. */
    onSave: (content: string) => Promise<unknown> | void;
}

/** Browses a folder tree; clicking a file loads it, Save writes it and keeps the dialog open. */
export interface FileBrowserOptions extends CommonOptions {
    root: CodeFolder;
    loadFile: (path: string) => Promise<string>;
    saveFile: (path: string, content: string) => Promise<unknown> | void;
    /** File opened when the dialog is created. */
    initialPath?: string;
}

export type CodeEditorModalOptions = SingleFileOptions | FileBrowserOptions;

type TreeItem = HTMLElement & { selected: boolean };

/** Folders this deep start expanded. */
const EXPANDED_DEPTH = 2;

/** Preferences remembered across dialogs. */
const THEME_STORAGE_KEY = 'examc:code-editor:theme';
const WRAP_STORAGE_KEY = 'examc:code-editor:wrap';

/** Languages guessed from a file's extension; others keep the selected language. */
const EXTENSION_LANGUAGES: Record<string, CodeLanguage> = {
    tex: 'latex',
    sty: 'latex',
    cls: 'latex',
    md: 'markdown',
    markdown: 'markdown',
    txt: 'plain',
};

/** Ids of the editors' labels: unique, since several dialogs can exist at once. */
let labelCount = 0;

function isBrowser(options: CodeEditorModalOptions): options is FileBrowserOptions {
    return 'root' in options;
}

/**
 * Guesses a file's language from its extension.
 *
 * @param {string} path - The file's path.
 * @return {CodeLanguage | undefined} The language, or undefined if the extension isn't known.
 */
function languageForPath(path: string): CodeLanguage | undefined {
    const name = path.split('/').pop() ?? '';
    const dot = name.lastIndexOf('.');
    return dot > 0 ? EXTENSION_LANGUAGES[name.slice(dot + 1).toLowerCase()] : undefined;
}

function loadPreference(key: string): string | null {
    try {
        return localStorage.getItem(key);
    } catch {
        return null; // storage unavailable: the default is used
    }
}

function savePreference(key: string, value: string): void {
    try {
        localStorage.setItem(key, value);
    } catch {
        // Storage unavailable: the choice just isn't remembered.
    }
}

/**
 * Fills a select with choices, the current one selected.
 *
 * @param {HTMLSelectElement} select - The select.
 * @param {Record<string, { label: string }>} choices - The choices, by value.
 * @param {string} current - The selected value.
 */
function fillSelect(select: HTMLSelectElement, choices: Record<string, { label: string }>, current: string): void {
    for (const [value, { label }] of Object.entries(choices)) {
        select.add(new Option(label, value, false, value === current));
    }
}

/**
 * Creates a tree item; the label is added as text, never as HTML.
 *
 * @param {string} filename - The item's label.
 * @param {string} icon - The Font Awesome icon name.
 * @return {TreeItem} The item.
 */
function treeItem(filename: string, icon: string): TreeItem {
    const iconEl = document.createElement('i');
    iconEl.className = `fas fa-${icon} me-1 text-muted`;
    iconEl.style.paddingRight = '.25rem';
    iconEl.setAttribute('aria-hidden', 'true');

    const labelEl = document.createElement('span');
    labelEl.textContent = filename;

    const item = document.createElement('wa-tree-item') as TreeItem;
    item.style.fontFamily = CODE_FONT_FAMILY;
    item.append(iconEl, labelEl);
    return item;
}

/**
 * Creates the tree item of a folder, with its subfolders and files.
 *
 * @param {CodeFolder} folder - The folder.
 * @param {number} depth - Its depth in the tree.
 * @return {TreeItem} The item.
 */
function folderItem(folder: CodeFolder, depth: number): TreeItem {
    const item = treeItem(folder.name, 'folder');
    if (depth < EXPANDED_DEPTH) item.setAttribute('expanded', '');

    for (const child of folder.folders ?? []) item.append(folderItem(child, depth + 1));
    for (const file of folder.files ?? []) {
        const fileItem = treeItem(file.name, 'file-lines');
        fileItem.dataset['path'] = file.path;
        item.append(fileItem);
    }
    return item;
}

/** A dialog editing text in a code editor, optionally beside a file tree; removed once closed. */
export class CodeEditorModal extends ExamcModal {
    private readonly editor: Promise<CodeEditor>;
    private editorInstance: CodeEditor | null = null;
    private readonly labelEl: HTMLLabelElement;
    private readonly statusEl: HTMLElement;
    private readonly saveButton: HTMLButtonElement;
    private readonly languageSelect: HTMLSelectElement;
    private statusTimer: number | undefined;

    /** Content as last loaded or saved: anything else is an unsaved change. */
    private savedContent = '';
    /** Browser mode: the file in the editor and its tree item. */
    private currentPath: string | null = null;
    private currentItem: TreeItem | null = null;
    /** Incremented on every file load, so a stale response is ignored. */
    private loadToken = 0;

    public constructor(private readonly options: CodeEditorModalOptions) {
        super(ExamcModal.createElement({
            maxWidth: '1750px',
            bodyContent: `
                <div class="modal-body">
                    <div class="row g-3 flex-nowrap">
                        <div class="col-4 border-end" data-tree-pane style="height:70vh;max-width: 25rem;overflow:auto;"></div>
                        <div class="col" style="min-width:0;">
                            <div class="d-flex align-items-center mb-2" style="gap:.5rem;">
                                <label class="form-label mb-0 text-break me-auto mr-auto"></label>
                                <button type="button" class="btn btn-outline-secondary btn-sm text-nowrap" data-wrap
                                        title="Wrap long lines">
                                    <i class="fas fa-arrow-turn-down" aria-hidden="true"></i> Wrap
                                </button>
                                <select class="form-select form-select-sm custom-select custom-select-sm w-auto"
                                        data-language aria-label="Highlighting" title="Highlighting"></select>
                                <select class="form-select form-select-sm custom-select custom-select-sm w-auto"
                                        data-theme aria-label="Theme" title="Theme"></select>
                            </div>
                            <div data-code-editor></div>
                        </div>
                    </div>
                </div>
            `,
            footerContent: `
                <span class="small text-muted me-auto mr-auto" data-status role="status"></span>
                <button type="button" class="btn btn-dark btn-sm" data-save>Save changes</button>
                <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Close</button>
            `,
        }));

        this.setTitle(options.title);

        this.labelEl = this.element.querySelector<HTMLLabelElement>('label')!;
        this.labelEl.id = `code-editor-label-${++labelCount}`;
        this.statusEl = this.element.querySelector<HTMLElement>('[data-status]')!;
        this.saveButton = this.element.querySelector<HTMLButtonElement>('[data-save]')!;

        // Language, theme and wrapping
        const language = options.language ?? 'plain';
        const savedTheme = loadPreference(THEME_STORAGE_KEY);
        const theme: CodeTheme = savedTheme && isCodeTheme(savedTheme) ? savedTheme : 'default';
        let lineWrapping = loadPreference(WRAP_STORAGE_KEY) !== 'false'; // on by default

        this.languageSelect = this.element.querySelector<HTMLSelectElement>('[data-language]')!;
        const themeSelect = this.element.querySelector<HTMLSelectElement>('[data-theme]')!;
        const wrapButton = this.element.querySelector<HTMLButtonElement>('[data-wrap]')!;
        fillSelect(this.languageSelect, CODE_LANGUAGES, language);
        fillSelect(themeSelect, CODE_THEMES, theme);

        const showWrapping = (): void => {
            wrapButton.classList.toggle('active', lineWrapping);
            wrapButton.setAttribute('aria-pressed', String(lineWrapping));
        };
        showWrapping();

        this.languageSelect.addEventListener('change', () => {
            const value = this.languageSelect.value;
            if (isCodeLanguage(value)) this.setLanguage(value);
        });
        themeSelect.addEventListener('change', () => {
            const value = themeSelect.value;
            if (!isCodeTheme(value)) return;
            savePreference(THEME_STORAGE_KEY, value);
            void this.editor.then((editor) => editor.setTheme(value));
        });
        wrapButton.addEventListener('click', () => {
            lineWrapping = !lineWrapping;
            showWrapping();
            savePreference(WRAP_STORAGE_KEY, String(lineWrapping));
            void this.editor.then((editor) => editor.setLineWrapping(lineWrapping));
        });

        // Editor
        const target = this.element.querySelector<HTMLElement>('[data-code-editor]')!;
        this.editor = CodeEditor.create({
            target,
            language,
            theme,
            lineWrapping,
            labelledBy: this.labelEl.id,
            height: isBrowser(options) ? '65vh' : '70vh',
        });
        void this.editor.then((editor) => (this.editorInstance = editor));

        // File tree
        const treePane = this.element.querySelector<HTMLElement>('[data-tree-pane]')!;
        if (isBrowser(options)) {
            this.labelEl.textContent = 'Select a file in the list.';
            this.saveButton.disabled = true;
            this.buildTree(treePane, options);
        } else {
            treePane.remove();
            this.labelEl.textContent = options.label; // text: a path is never interpreted as HTML
        }

        // The editor's content isn't a form field: clicking the label focuses it explicitly.
        this.labelEl.addEventListener('click', () => void this.editor.then((editor) => editor.focus()));
        this.saveButton.addEventListener('click', () => void this.save());

        // Ctrl/Cmd+S saves instead of saving the web page.
        this.element.addEventListener('keydown', (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
                event.preventDefault();
                if (!this.saveButton.disabled) void this.save();
            }
        });

        this.element.addEventListener('hide.bs.modal', (event) => {
            if (this.isDirty() && !window.confirm('Close without saving your changes?')) event.preventDefault();
        });
        this.element.addEventListener('shown.bs.modal', () => void this.editor.then((editor) => {
            editor.refresh();
            if (!isBrowser(this.options) || this.currentPath) editor.focus();
        }));
        this.element.addEventListener('hidden.bs.modal', () => void this.editor.then((editor) => editor.destroy()));
    }

    /**
     * Shows the dialog; in single file mode, on some content.
     *
     * @param {string} [content] - The content to edit (single file mode).
     */
    public async open(content?: string): Promise<void> {
        if (content !== undefined) await this.setContent(content);
        this.show();
    }

    /** Replaces the editor's content, which then counts as saved. */
    public async setContent(content: string): Promise<void> {
        (await this.editor).setContent(content);
        this.savedContent = content;
    }

    /** Changes the highlighted language, and the select showing it. */
    private setLanguage(language: CodeLanguage): void {
        this.languageSelect.value = language;
        void this.editor.then((editor) => editor.setLanguage(language));
    }

    private isDirty(): boolean {
        return this.editorInstance !== null && this.editorInstance.getContent() !== this.savedContent;
    }

    private setStatus(text: string, options?: { clearAfterMs?: number }): void {
        window.clearTimeout(this.statusTimer);
        this.statusEl.textContent = text;
        if (options?.clearAfterMs) {
            this.statusTimer = window.setTimeout(() => (this.statusEl.textContent = ''), options.clearAfterMs);
        }
    }

    private buildTree(pane: HTMLElement, options: FileBrowserOptions): void {
        const tree = document.createElement('wa-tree');
        tree.setAttribute('selection', 'leaf'); // only files are selectable; folders expand
        tree.append(folderItem(options.root, 0));

        tree.addEventListener('wa-selection-change', (event) => {
            const [item] = (event as CustomEvent<{ selection: TreeItem[] }>).detail.selection;
            const path = item?.dataset['path'];
            if (item && path && path !== this.currentPath) void this.openFile(path, item);
        });
        pane.append(tree);

        if (options.initialPath) {
            const item = tree.querySelector<TreeItem>(`wa-tree-item[data-path="${CSS.escape(options.initialPath)}"]`);
            if (item) {
                item.selected = true;
                for (
                    let parent = item.parentElement?.closest('wa-tree-item');
                    parent;
                    parent = parent.parentElement?.closest('wa-tree-item')
                ) {
                    parent.setAttribute('expanded', '');
                }
            }
            void this.openFile(options.initialPath, item ?? null);
        }
    }

    /** Puts the tree's selection back on the file in the editor. */
    private restoreSelection(rejected: TreeItem | null): void {
        if (rejected) rejected.selected = false;
        if (this.currentItem) this.currentItem.selected = true;
    }

    private async openFile(path: string, item: TreeItem | null): Promise<void> {
        if (!isBrowser(this.options)) return;

        if (this.isDirty() && !window.confirm('Discard your unsaved changes?')) {
            this.restoreSelection(item);
            return;
        }

        const token = ++this.loadToken;
        this.saveButton.disabled = true;
        this.setStatus('Loading…');

        try {
            const content = await this.options.loadFile(path);
            if (token !== this.loadToken) return;

            await this.setContent(content);

            const detected = languageForPath(path);
            if (detected) this.setLanguage(detected);

            this.currentPath = path;
            this.currentItem = item;
            this.labelEl.textContent = path;
            this.setStatus('');
            (await this.editor).focus();
        } catch (error) {
            if (token !== this.loadToken) return;
            console.error(error);
            this.setStatus('The file could not be opened. Please try again.');
            this.restoreSelection(item);
        } finally {
            if (token === this.loadToken) this.saveButton.disabled = this.currentPath === null;
        }
    }

    private async save(): Promise<void> {
        const content = (await this.editor).getContent();
        const path = this.currentPath; // the file may change while saving
        this.saveButton.disabled = true;

        try {
            if (isBrowser(this.options)) {
                if (!path) return;
                await this.options.saveFile(path, content);
                if (path === this.currentPath) this.savedContent = content;
                this.setStatus('Saved.', { clearAfterMs: 3000 });
            } else {
                await this.options.onSave(content);
                this.savedContent = content; // before hide(): no "unsaved changes" prompt
                this.hide();
            }
        } catch (error) {
            console.error(error);
            this.setStatus('The changes could not be saved. Please try again.');
        } finally {
            this.saveButton.disabled = isBrowser(this.options) && this.currentPath === null;
        }
    }
}