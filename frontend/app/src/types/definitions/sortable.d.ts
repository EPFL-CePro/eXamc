export interface SortableOptions {
    handle?: string;
    draggable?: string;
    animation?: number;
    onEnd?: () => void;
}

export interface SortableInstance {
    destroy(): void;
}

declare global {
    /** SortableJS, loaded by a <script> of the page (CDN). */
    const Sortable: {
        create(element: HTMLElement, options?: SortableOptions): SortableInstance;
    };
}
