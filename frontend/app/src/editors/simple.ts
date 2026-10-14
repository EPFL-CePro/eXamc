import { Crepe, type CrepeConfig } from '@milkdown/crepe';
import { editorViewCtx } from '@milkdown/kit/core';
import { getHTML, getMarkdown, replaceAll } from '@milkdown/kit/utils';

import '@milkdown/crepe/theme/common/style.css';
import '@milkdown/crepe/theme/frame.css';

import { BaseEditor } from './base.ts';

const DEFAULT_EDITOR_OPTIONS: CrepeConfig = {
    features: {
        [Crepe.Feature.BlockEdit]: false, // no drag handle, "+" button or slash menu
        [Crepe.Feature.ImageBlock]: false,
        [Crepe.Feature.TopBar]: true,
    },
};

/** A formatted text editor (Milkdown Crepe): bold, lists, titles, simple formulas. */
export class SimpleEditor extends BaseEditor {
    private constructor(target: HTMLElement, public readonly crepe: Crepe) {
        super(target);
    }

    /**
     * Creates a simple editor on an element, or returns the one it already has.
     *
     * @param {Object} options - The editor's options.
     * @param {HTMLElement} options.target - The element the editor is created in.
     * @param {string} [options.defaultValue] - The initial content, as Markdown.
     * @return {Promise<SimpleEditor>} The editor, once ready.
     */
    public static create({ target, defaultValue = '' }: { target: HTMLElement; defaultValue?: string }): Promise<SimpleEditor> {
        return BaseEditor.attach(target, async () => {
            const crepe = new Crepe({ ...DEFAULT_EDITOR_OPTIONS, root: target, defaultValue });
            await crepe.create();
            return new SimpleEditor(target, crepe);
        });
    }

    /**
     * The edited content.
     *
     * @param {"html" | "markdown"} [format="html"] - The format to return.
     * @return {string} The content in that format.
     */
    public getContent(format: 'html' | 'markdown' = 'html'): string {
        return this.crepe.editor.action(format === 'html' ? getHTML() : getMarkdown());
    }

    /**
     * Replaces the edited content.
     *
     * @param {string} content - The new content, as Markdown.
     */
    public setContent(content: string): void {
        this.crepe.editor.action(replaceAll(content));
    }

    public focus(): void {
        this.crepe.editor.action((ctx) => ctx.get(editorViewCtx).focus());
    }

    protected dispose(): void {
        void this.crepe.destroy();
    }
}