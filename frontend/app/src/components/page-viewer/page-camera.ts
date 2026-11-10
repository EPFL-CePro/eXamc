import Konva from 'konva';

/** Space around the whole page, so its shadow shows. */
const PAGE_MARGIN = 16;

interface Size {
    width: number;
    height: number;
}

/**
 * Zoom and pan of a stage over a page: the page always stays in view, and zoom goes from
 * "whole page" up to `maxZoom()` times that.
 */
export class PageCamera {
    /** Scale showing the whole page; zoom is relative to it. */
    private fitScale = 1;

    /**
     * @param {Konva.Stage} stage - The stage, scaled and moved by the camera.
     * @param {() => Size} pageSize - The page's size, in page units.
     * @param {() => number} maxZoom - Maximum zoom, relative to the whole page.
     */
    public constructor(
        private readonly stage: Konva.Stage,
        private readonly pageSize: () => Size,
        private readonly maxZoom: () => number,
    ) {}

    public get scale(): number {
        return this.stage.scaleX();
    }

    /** Shows the whole page. */
    public fit(): void {
        this.fitScale = this.computeFitScale();
        this.stage.scale({ x: this.fitScale, y: this.fitScale });
        this.stage.position(this.clamp({ x: 0, y: 0 }));
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

    public pan(dx: number, dy: number): void {
        this.stage.position(this.clamp({ x: this.stage.x() + dx, y: this.stage.y() + dy }));
    }

    /** Resizes the stage, keeping the zoom level. */
    public resize({ width, height }: Size): void {
        if (width === this.stage.width() && height === this.stage.height()) return;
        const zoom = this.scale / this.fitScale;
        this.stage.size({ width, height });
        this.fitScale = this.computeFitScale();
        this.zoomTo(this.fitScale * zoom);
    }

    /** Keeps the page in view: centered while smaller than the viewer, edges never pulled in once larger. */
    public clamp(pos: Konva.Vector2d): Konva.Vector2d {
        const page = this.pageSize();
        const scale = this.scale;
        const clampAxis = (value: number, content: number, view: number): number =>
            content <= view ? (view - content) / 2 : Math.min(0, Math.max(view - content, value));
        return {
            x: clampAxis(pos.x, page.width * scale, this.stage.width()),
            y: clampAxis(pos.y, page.height * scale, this.stage.height()),
        };
    }

    private computeFitScale(): number {
        const page = this.pageSize();
        if (!page.width || !page.height) return 1;
        const room = (size: number): number => Math.max(size - 2 * PAGE_MARGIN, 1);
        return Math.min(room(this.stage.width()) / page.width, room(this.stage.height()) / page.height);
    }
}
