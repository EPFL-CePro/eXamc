import tinymce, { type Editor, type RawEditorOptions } from 'tinymce';

import 'tinymce/icons/default/icons.min.js';
import 'tinymce/themes/silver/theme.min.js';
import 'tinymce/models/dom/model.min.js';

// UI skin (toolbar, menus, dialogs): a normal stylesheet in the page
import 'tinymce/skins/ui/oxide/skin.min.css';
// Styles for inside the editing iframe, imported as strings
import contentUiCss from 'tinymce/skins/ui/oxide/content.min.css?inline';
import contentCss from 'tinymce/skins/content/default/content.min.css?inline';

import 'tinymce/plugins/link';
import 'tinymce/plugins/lists';
import 'tinymce/plugins/code';

type TinyMceEditorOptions = Omit<RawEditorOptions, 'target' | 'selector'>;

interface InitTinyMceOptions {
    target: HTMLElement;
    editorOptions?: TinyMceEditorOptions;
}


const BUNDLED_CONTENT_STYLE = `${contentUiCss}\n${contentCss}`;

const DEFAULT_EDITOR_OPTIONS: TinyMceEditorOptions = {
    license_key: 'gpl',
    menubar: false,
    promotion: false,
    branding: false,
    height: 300,
    plugins: 'link lists code',
    toolbar: 'bold italic underline removeformat | bullist numlist | alignleft aligncenter | link | code',
    // Never fetch skins or content CSS from a URL: everything is bundled.
    skin: false,
    content_css: false,
};


const editors = new WeakMap<HTMLElement, Promise<Editor>>();

/**
 * Initializes TinyMCE on `target`, or returns the existing editor if it's already initialized
 * (or being initialized). `editorOptions` only apply the first time.
 */
export function initTinyMce({ target, editorOptions = {} }: InitTinyMceOptions): Promise<Editor> {
    const existing = editors.get(target);
    if (existing) return existing;

    const pending = createTinyMce(target, editorOptions);
    editors.set(target, pending);

    // If initialization fails, forget it so a later call can retry.
    pending.catch(() => editors.delete(target));

    return pending;
}

async function createTinyMce(target: HTMLElement, editorOptions: TinyMceEditorOptions): Promise<Editor> {
    // setup and content_style are combined with the defaults instead of replacing them.
    const { setup, content_style, ...overrides } = editorOptions;

    const [editor] = await tinymce.init({
        ...DEFAULT_EDITOR_OPTIONS,
        ...overrides,
        target,
        content_style: content_style ? `${BUNDLED_CONTENT_STYLE}\n${content_style}` : BUNDLED_CONTENT_STYLE,
        setup: (editor) => {
            // Keep a textarea target in sync so FormData(form) picks up the content.
            editor.on('change input undo redo', () => editor.save());
            // Once the editor is removed (editor.remove() / tinymce.remove()), allow re-initializing.
            editor.on('remove', () => editors.delete(target));
            setup?.(editor);
        },
    });

    if (!editor) throw new Error('TinyMCE failed to initialize');
    return editor;
}