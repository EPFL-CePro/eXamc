import Konva from 'konva';

/** Space around the content, in screen pixels, so the shadows show. */
const MARGIN = 16;

export interface Size {
    width: number;
    height: number;
}

/** How "fit" sizes the pages: a whole page in view, or the pages' width filling the viewer. */
export type FitMode = 'page' | 'width';

/**
 * Zoom and scroll of a stage over a column of pages. The content always stays in view (centered while
 * smaller than the viewer), and zoom goes from "fit" up to `maxZoom()` times that.
 */
export class PageCamera {
    /** Scale of "fit"; zoom is relative to it. */
    private fitScale = 1;

    /**
     * @param {Konva.Stage} stage - The stage, scaled and moved by the camera.
     * @param {() => Size} contentSize - All the pages, gaps included, in content units.
     * @param {() => Size} pageSize - The largest page, in content units.
     * @param {() => number} maxZoom - Maximum zoom, relative to fit.
     * @param {() => FitMode} fitMode - What fit means.
     */
    public constructor(
        private readonly stage: Konva.Stage,
        private readonly contentSize: () => Size,
        private readonly pageSize: () => Size,
        private readonly maxZoom: () => number,
        private readonly fitMode: () => FitMode,
    ) {}

    public get scale(): number {
        return this.stage.scaleX();
    }

    /** The content's y (in content units) at the middle of the viewer. */
    public get centerY(): number {
        return (this.stage.height() / 2 - this.stage.y()) / this.scale;
    }

    /** Fits the pages and shows the first one (new content). */
    public reset(): void {
        this.fitScale = this.computeFitScale();
        this.stage.scale({ x: this.fitScale, y: this.fitScale });
        this.scrollTo(0);
    }

    /** Fits the pages, keeping the content at the top of the viewer in place. */
    public fit(): void {
        const top = this.topY();
        this.fitScale = this.computeFitScale();
        this.stage.scale({ x: this.fitScale, y: this.fitScale });
        this.scrollTo(top);
    }

    /** Zooms to a scale, keeping a viewer point (default: the center) in place. */
    public zoomTo(scale: number, center?: Konva.Vector2d): void {
        const target = Math.min(Math.max(scale, this.fitScale), this.fitScale * this.maxZoom());
        const point = center ?? { x: this.stage.width() / 2, y: this.stage.height() / 2 };
        const old = this.scale;
        const anchor = { x: (point.x - this.stage.x()) / old, y: (point.y - this.stage.y()) / old };

        this.stage.scale({ x: target, y: target });
        this.stage.position(this.clamp({ x: point.x - anchor.x * target, y: point.y - anchor.y * target }));
    }

    public zoomBy(factor: number, center?: Konva.Vector2d): void {
        this.zoomTo(this.scale * factor, center);
    }

    /** Moves the content by screen pixels. */
    public pan(dx: number, dy: number): void {
        this.stage.position(this.clamp({ x: this.stage.x() + dx, y: this.stage.y() + dy }));
    }

    /** Scrolls so a content y (e.g. a page's top) is at the top of the viewer, below the margin. */
    public scrollTo(contentY: number): void {
        this.stage.position(this.clamp({ x: this.stage.x(), y: MARGIN - contentY * this.scale }));
    }

    /** Resizes the stage, keeping the zoom level and the content at the top in place. */
    public resize({ width, height }: Size): void {
        if (width === this.stage.width() && height === this.stage.height()) return;
        const top = this.topY();
        const zoom = this.scale / this.fitScale;
        this.stage.size({ width, height });
        this.fitScale = this.computeFitScale();
        this.stage.scale({ x: this.fitScale * zoom, y: this.fitScale * zoom });
        this.scrollTo(top);
    }

    /** Keeps the content in view: centered while smaller than the viewer, a margin at its ends otherwise. */
    public clamp(pos: Konva.Vector2d): Konva.Vector2d {
        const content = this.contentSize();
        const scale = this.scale;
        const clampAxis = (value: number, length: number, view: number): number =>
            length + 2 * MARGIN <= view
                ? (view - length) / 2
                : Math.min(MARGIN, Math.max(view - length - MARGIN, value));
        return {
            x: clampAxis(pos.x, content.width * scale, this.stage.width()),
            y: clampAxis(pos.y, content.height * scale, this.stage.height()),
        };
    }

    /** The content's y at the top of the viewer, below the margin. */
    public topY(): number {
        return (MARGIN - this.stage.y()) / this.scale;
    }

    private computeFitScale(): number {
        const page = this.pageSize();
        if (!page.width || !page.height) return 1;
        const room = (size: number): number => Math.max(size - 2 * MARGIN, 1);
        const widthScale = room(this.stage.width()) / page.width;
        return this.fitMode() === 'width' ? widthScale : Math.min(widthScale, room(this.stage.height()) / page.height);
    }
}