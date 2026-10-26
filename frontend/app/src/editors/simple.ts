import { Crepe, type CrepeConfig } from '@milkdown/crepe';
import { defaultValueCtx, editorViewCtx, schemaCtx } from '@milkdown/kit/core';
import { DOMParser as ProseMirrorDOMParser } from '@milkdown/kit/prose/model';
import { getHTML, getMarkdown, replaceAll } from '@milkdown/kit/utils';

import '@milkdown/crepe/theme/common/style.css';
import '@milkdown/crepe/theme/frame.css';

import { BaseEditor } from './base.ts';

import "./simple.scss";
import type { SimpleEditorFormat } from '@examc/types/editors.ts';

const DEFAULT_EDITOR_OPTIONS: CrepeConfig = {
    features: {
        [Crepe.Feature.BlockEdit]: false, // no drag handle, "+" button or slash menu
        [Crepe.Feature.ImageBlock]: false,
        [Crepe.Feature.TopBar]: true,
    },
};


/**
 * Parses HTML in an inert document: unlike innerHTML on an element of the page,
 * nothing in it runs or loads, such as scripts or an image's onerror handler.
 */
function parseHtml(html: string): HTMLElement {
    return new DOMParser().parseFromString(html, 'text/html').body;
}


/** A formatted text editor (Milkdown Crepe): bold, lists, titles, simple formulas. */
export class SimpleEditor extends BaseEditor {
    private format: SimpleEditorFormat;

    private constructor(target: HTMLElement, public readonly crepe: Crepe, format: SimpleEditorFormat) {
        super(target);
        this.format = format;
    }

       /**
     * Creates a simple editor on an element, or returns the one it already has.
     *
     * @param {Object} options - The editor's options.
     * @param {HTMLElement} options.target - The element the editor is created in.
     * @param {string} [options.defaultValue] - The initial content, in `format`.
     * @param {SimpleEditorFormat} [options.format="markdown"] - The format of the content, in and out.
     * @param {Function} [options.onChange] - Called with the content, in `format`, after it changes.
     * @return {Promise<SimpleEditor>} The editor, once ready.
     */
    public static create({ target, defaultValue = '', format = "markdown", onChange }: {
        target: HTMLElement;
        defaultValue?: string;
        format?: SimpleEditorFormat;
        onChange?: (content: string) => void;
    }): Promise<SimpleEditor> {
        return BaseEditor.attach(target, async () => {
            // The Markdown default is only set for Markdown content; HTML is set through defaultValueCtx below.
            const crepe = new Crepe({
                ...DEFAULT_EDITOR_OPTIONS,
                root: target,
                defaultValue: format === "markdown" ? defaultValue : ""
            });

            if (format === 'html') {
                // Registered after Crepe's own configuration, so it replaces the empty Markdown default.
                crepe.editor.config((ctx) => ctx.set(defaultValueCtx, { type: 'html', dom: parseHtml(defaultValue) }));
            }
            if (onChange) {
                crepe.on((listener) => {
                    listener.markdownUpdated((ctx, markdown) => {
                        onChange(format === 'html' ? getHTML()(ctx) : markdown);
                    });
                });
            }
            await crepe.create();

            return new SimpleEditor(target, crepe, format);
        });
    }
    
    /**
     * The edited content.
     *
     * @param {SimpleEditorFormat} [format="html"] - The format to return, if unset, uses the one set by create method.
     * @return {string} The content in that format.
     */
    public getContent(format?: SimpleEditorFormat): string {
        format = format ?? this.format;
        return this.crepe.editor.action(format === 'html' ? getHTML() : getMarkdown());
    }

    /**
     * Replaces the edited content.
     *
     * @param {string} content - The new content.
     * @param {SimpleEditorFormat} [format] - The new content's format; if unset, the one given to `create`.
     */
    public setContent(content: string, format?: SimpleEditorFormat): void {
        if ((format ?? this.format) === 'markdown') {
            this.crepe.editor.action(replaceAll(content));
            return;
        }
        this.crepe.editor.action((ctx) => {
            const view = ctx.get(editorViewCtx);
            const doc = ProseMirrorDOMParser.fromSchema(ctx.get(schemaCtx)).parse(parseHtml(content));
            view.dispatch(view.state.tr.replaceWith(0, view.state.doc.content.size, doc.content));
        });
    }

    public focus(): void {
        this.crepe.editor.action((ctx) => ctx.get(editorViewCtx).focus());
    }

    protected dispose(): void {
        void this.crepe.destroy();
    }
}