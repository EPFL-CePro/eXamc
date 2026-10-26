/**
 * An editor attached to a page element: shared behavior of the project's editors (simple text, code).
 * Each element holds at most one editor: creating one on an element that already has one returns the existing one.
 */
export abstract class BaseEditor {
    /** The editor of each element, while it's being created and once it's ready. */
    private static readonly instances = new WeakMap<HTMLElement, Promise<BaseEditor>>();

    protected constructor(protected readonly target: HTMLElement) {}

    /**
     * Creates the editor of an element once; later calls for the same element return the same editor.
     * If creation fails, it's forgotten, so a retry is possible.
     *
     * @param {HTMLElement} target - The element the editor is attached to.
     * @param {() => Promise<E>} create - Creates the editor.
     * @return {Promise<E>} The editor, once ready.
     */
    protected static attach<E extends BaseEditor>(target: HTMLElement, create: () => Promise<E>): Promise<E> {
        const existing = BaseEditor.instances.get(target);
        if (existing) return existing as Promise<E>;

        const ready = create();
        BaseEditor.instances.set(target, ready);
        ready.catch(() => BaseEditor.instances.delete(target));
        return ready;
    }

    /** The edited content. */
    public abstract getContent(): string;

    /**
     * Replaces the edited content.
     *
     * @param {string} content - The new content.
     */
    public abstract setContent(content: string): void;

    /** Puts the keyboard focus in the editor. */
    public abstract focus(): void;

    /** Removes the editor from its element; a new one can then be created there. */
    public destroy(): void {
        BaseEditor.instances.delete(this.target);
        this.dispose();
    }

    /** Releases what the underlying editor library created. */
    protected abstract dispose(): void;
}