/**
 * A shape drawn over the page, in image pixels: corners as [x1, y1, x2, y2, ...] (closed).
 * `data` is anything the page needs back when the shape is clicked.
 */
export interface PageShape<T = unknown> {
    points: number[];
    data: T;
    stroke?: string;
    strokeWidth?: number;
    dash?: number[];
    fill?: string;
}

/** Detail of the `shape-click` event. */
export interface ShapeClickDetail<T = unknown> {
    shape: PageShape<T>;
}

/** A viewer command, from the toolbar or the keyboard. */
export type ViewerCommand =
    | { type: 'zoom-in' }
    | { type: 'zoom-out' }
    | { type: 'fit' }
    | { type: 'pan'; dx: number; dy: number };
