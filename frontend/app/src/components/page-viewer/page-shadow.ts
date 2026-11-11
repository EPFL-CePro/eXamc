import Konva from 'konva';

/**
 * Soft shadow under each page, in screen pixels at any zoom: stacked translucent rounded rectangles,
 * much cheaper to redraw than a canvas blur.
 */
const SHADOW = { spread: 12, offsetY: 3, steps: 8, alpha: 0.03 };
const ANIMATION_MS = 220;
const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)');

export interface Rect {
    x: number;
    y: number;
    width: number;
    height: number;
}

/** The pages' drop shadows, which can retract under the pages and spread out again. */
export class PageShadow {
    public readonly node = new Konva.Shape({ listening: false });

    private rects: Rect[] = [];
    /** How far the shadows are out: 0 = retracted under the pages, 1 = full. */
    private level = 1;
    private target = 1;
    private frame = 0;

    public constructor() {
        this.node.sceneFunc((context, shape) => this.draw(context, shape));
    }

    /** The pages to draw a shadow under, in content coordinates. */
    public setRects(rects: Rect[]): void {
        this.rects = rects;
        this.node.getLayer()?.batchDraw();
    }

    public retract(): void {
        this.animateTo(0);
    }

    public restore(): void {
        this.animateTo(1);
    }

    /** Rounded rectangles growing outwards and overlapping, darkest at each page's edge. */
    private draw(context: Konva.Context, shape: Konva.Shape): void {
        const level = this.level * this.level * (3 - 2 * this.level); // smoothstep
        if (level <= 0 || this.rects.length === 0) return;

        const px = 1 / shape.getAbsoluteScale().x; // one screen pixel, in content units
        const { spread, offsetY, steps, alpha } = SHADOW;
        context.setAttr('fillStyle', `rgba(0, 0, 0, ${alpha * level})`);
        for (const rect of this.rects) {
            for (let step = 1; step <= steps; step++) {
                const grow = (spread * level * step / steps) * px;
                context.beginPath();
                context.roundRect(
                    rect.x - grow, rect.y - grow + offsetY * level * px,
                    rect.width + 2 * grow, rect.height + 2 * grow, grow,
                );
                context.fill();
            }
        }
    }

    /** Moves towards a level; a new target set mid-way turns the animation around. */
    private animateTo(target: number): void {
        this.target = target;
        if (REDUCED_MOTION.matches) {
            this.level = target;
            this.node.getLayer()?.batchDraw();
            return;
        }
        if (this.frame) return;

        let last = performance.now();
        const step = (now: number): void => {
            const delta = (now - last) / ANIMATION_MS;
            last = now;
            this.level = this.target > this.level
                ? Math.min(this.target, this.level + delta)
                : Math.max(this.target, this.level - delta);
            this.node.getLayer()?.batchDraw();
            this.frame = this.level === this.target ? 0 : requestAnimationFrame(step);
        };
        this.frame = requestAnimationFrame(step);
    }
}