/**
 * A shape drawn over a page, in that page's image pixels: corners as [x1, y1, x2, y2, ...] (closed).
 * `data` is anything the caller needs back when the shape is clicked.
 */
export interface PageShape<T = unknown> {
    points: number[];
    data: T;
    stroke?: string;
    strokeWidth?: number;
    dash?: number[];
    fill?: string;
}

/** One page of the document: its image, and the shapes drawn over it. */
export interface ViewerPage<T = unknown> {
    image: HTMLImageElement;
    shapes?: PageShape<T>[];
    /** Shown in the page indicator while this page is the current one (default: "Page 3 / 12"). */
    label?: string;
    /**
     * A divider drawn above this page, e.g. where a new copy starts: `end` closes the part above,
     * `start` opens this one.
     */
    divider?: { end: string; start: string } | undefined;
}

/** Loads a page of the document when the viewer needs it (index from 0). */
export type PageLoader<T = unknown> = (index: number) => Promise<ViewerPage<T>>;

/** Detail of the `shape-click` event. */
export interface ShapeClickDetail<T = unknown> {
    shape: PageShape<T>;
    /** Index of the page the shape is on. */
    page: number;
}

/** Detail of the `page-change` event: the page in the middle of the viewer. */
export interface PageChangeDetail {
    page: number;
    count: number;
}

/** A viewer command, from the toolbar or the keyboard. */
export type ViewerCommand =
    | { type: 'zoom-in' }
    | { type: 'zoom-out' }
    | { type: 'fit' }
    | { type: 'pan'; dx: number; dy: number }
    | { type: 'page'; to: 'previous' | 'next' | 'first' | 'last' };