export type AdvancedEditorMode = 'wysiwyg' | 'source';

export interface AdvancedEditor {
    getMarkdown(): string;
    getMode(): AdvancedEditorMode;
    setMode(mode: AdvancedEditorMode): void;
    destroy(): void;
}

export type SimpleEditorFormat = 'html' | 'markdown';