import { Editor, type EditorOptions } from '@toast-ui/editor';

import '@toast-ui/editor/dist/toastui-editor.css';

type ToastUiEditorOptions = Omit<EditorOptions, 'el'>;

interface InitToastUiEditorOptions {
    target: HTMLElement;
    editorOptions?: Partial<ToastUiEditorOptions>;
}


const DEFAULT_EDITOR_OPTIONS: Partial<ToastUiEditorOptions> = {
    initialEditType: 'wysiwyg',
    previewStyle: 'vertical',
    height: '300px',
    // Never send usage statistics to NHN.
    usageStatistics: false,
};


/**
 * Creates a Toast UI markdown editor inside `target`.
 * `editorOptions` are combined with the defaults instead of replacing them.
 */
export function initToastUiEditor({ target, editorOptions = {} }: InitToastUiEditorOptions): Editor {
    return new Editor({
        ...DEFAULT_EDITOR_OPTIONS,
        ...editorOptions,
        el: target,
    });
}
