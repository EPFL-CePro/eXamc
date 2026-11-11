import Konva from 'konva';

import type {} from '../resize-handle/index.ts'; // types only: its resize-start / resize-end events

import { keyCommand } from './keyboard.ts';
import { PageCamera, type FitMode } from './page-camera.ts';
import { PageShadow } from './page-shadow.ts';
import { createShapeNode } from './shapes.ts';
import { render, type ViewerParts } from './template.ts';
import type { PageChangeDetail, PageLoader, PageShape, ShapeClickDetail, ViewerCommand, ViewerPage } from './types.ts';

const DEFAULT_ZOOM_STEP = 1.25;
const DEFAULT_MAX_ZOOM = 8;
/** Gap between pages, relative to the widest page's width. */
const PAGE_GAP_RATIO = 0.03;
/** Wheel deltas in lines (Firefox) or pages, in pixels. */
const WHEEL_LINE = 16;
/** Pages rendered on each side of the current one (with their shadow); the others are only laid out. */
const RENDERED_AROUND = 1;
/** Height of a divider between two parts of the document, relative to the widest page's width. */
const DIVIDER_RATIO = 0.14;
/** Font size of a divider's texts, relative to the widest page's width. */
const DIVIDER_FONT_RATIO = 0.022;
/** Size of a page that couldn't be loaded before any other was (A4's proportions). */
const FALLBACK_PAGE = { width: 1240, height: 1754 };

/** Logs a page's loading error; returns what to show in its place (eXamc errors' detail, or the message). */
function pageError(index: number, error: unknown): string {
    console.error(`Page ${index + 1} couldn't be loaded`, error);
    const { detail, message } = (error ?? {}) as { detail?: string; message?: string };
    return detail || message || 'Unknown error';
}

/** A page of the document: its place in the column, and once loaded, its content and (while rendered) its nodes. */
interface PageSlot {
    width: number;
    height: number;
    x: number;
    top: number;
    /** Whether a divider is drawn above the page (known once the page is loaded). */
    divider: boolean;
    content?: ViewerPage<unknown> | undefined;
    /** Why the page couldn't be loaded; a notice is drawn in its place. */
    error?: string | undefined;
    loading?: Promise<void> | undefined;
    group?: Konva.Group | undefined;
}

/**
 * `<examc-page-viewer>`: pages shown one under the other, like a PDF reader, with clickable shapes over
 * them, zoom (Ctrl + wheel, keys, toolbar), scrolling (wheel, drag, Page Up / Down) and soft page shadows.
 * Pages are loaded on demand through a loader, and only the current page and its neighbours are rendered.
 * It takes the size its element is given, and uses the page's Bootstrap and Font Awesome.
 *
 * Attributes: `zoom-step` (default 1.25), `max-zoom` (relative to fit, default 8),
 * `fit` ("page": a whole page in view, the default; "width": the pages fill the viewer's width).
 * Children: `slot="toolbar"` (secondary toolbar, top left), `slot="help"` (extra `<li>` help lines).
 * Events: `shape-click` (detail: `{ shape, page }`), `page-change` (detail: `{ page, count }`, the page
 * in the middle of the viewer). While an `<examc-resize-handle>` resizes it, the shadows tuck under the pages.
 */
export class PageViewerElement extends HTMLElement {
    private parts: ViewerParts | null = null;
    private readonly resizeObserver = new ResizeObserver(() => {
        this.camera?.resize(this.stageSize());
        this.updateCurrentPage();
    });

    private readonly layer = new Konva.Layer();
    private readonly shadow = new PageShadow();
    private readonly content = new Konva.Group();
    private slots: PageSlot[] = [];
    private loader: PageLoader<unknown> | null = null;
    /** Incremented by every setPages(), so pages loaded for a previous document are dropped. */
    private generation = 0;
    private contentSize = { width: 0, height: 0 };
    private largestPage = { width: 0, height: 0 };
    private camera: PageCamera | null = null;
    private current = -1;

    /** Built on first connection, when the page's children are there. */
    public connectedCallback(): void {
        if (!this.parts) {
            this.classList.add('d-block', 'position-relative', 'overflow-hidden', 'focus-ring');
            if (!this.hasAttribute('tabindex')) this.tabIndex = 0; // focusable, for the shortcuts
            this.parts = render(this);
            this.addEventListener('resize-start', () => this.shadow.retract());
            this.addEventListener('resize-end', () => this.shadow.restore());
            this.querySelectorAll<HTMLElement>('[data-command]').forEach((button) => {
                button.addEventListener('click', () => this.run({ type: button.dataset['command'] as 'zoom-in' | 'zoom-out' | 'fit' }));
            });
            this.addEventListener('keydown', (event) => this.handleKey(event));
            this.createStage(this.parts.stage);
        }
        this.resizeObserver.observe(this.parts.stage);
    }

    public disconnectedCallback(): void {
        this.resizeObserver.disconnect();
    }

    // -----------------------------------------------------------------------
    // Content
    // -----------------------------------------------------------------------

    /**
     * Shows a document of `count` pages, starting on page `start`. Pages are loaded through `loader` when
     * they come near the view, and kept once loaded; only the current page and its neighbours are rendered.
     * Until a page is loaded, it takes the size of the first page loaded. A page that can't be loaded
     * shows a notice in its place (the error is logged).
     *
     * @return {Promise<void>} Resolves once the start page is shown, or its notice.
     */
    public async setPages<T>(count: number, loader: PageLoader<T>, start = 0): Promise<void> {
        const generation = ++this.generation;
        this.content.destroyChildren();
        this.slots = [];
        this.loader = null;
        this.current = -2; // "unknown": the next updateCurrentPage() announces the page, even -1
        this.layout();
        if (count <= 0) {
            this.updateCurrentPage();
            return;
        }

        const first = Math.max(0, Math.min(start, count - 1));
        let error: string | undefined;
        const page = await loader(first).catch((reason: unknown) => {
            error = pageError(first, reason);
            return null;
        });
        if (generation !== this.generation) return;

        // Every page takes the start page's size until it's loaded itself
        const size = page ? { width: page.image.width, height: page.image.height } : FALLBACK_PAGE;
        this.loader = loader as PageLoader<unknown>;
        this.slots = Array.from({ length: count }, () => ({ ...size, x: 0, top: 0, divider: false }));
        const startSlot = this.slots[first]!;
        startSlot.content = page ?? undefined;
        startSlot.error = error;
        startSlot.divider = !!page?.divider && first > 0;
        this.layout();
        this.camera?.reset();
        this.scrollToPage(first);
    }

    /** Shows a single page; null clears the viewer. */
    public setImage(image: HTMLImageElement | null): void {
        void this.setPages(image ? 1 : 0, async () => ({ image: image! }));
    }

    /** Replaces the shapes drawn over a loaded page (the view stays as it is). */
    public setShapes<T>(shapes: PageShape<T>[], page = 0): void {
        const slot = this.slots[page];
        if (!slot?.content) return;
        slot.content = { ...slot.content, shapes: shapes as PageShape<unknown>[] };
        if (slot.group) {
            this.unrender(slot);
            this.renderSlot(slot, page);
        }
        this.layer.batchDraw();
    }

    /** Removes the pages and their shapes. */
    public clear(): void {
        void this.setPages(0, async () => Promise.reject(new Error('No pages')));
    }

    /** Shows a message over the viewer (placeholder, error); null hides it. */
    public showMessage(text: string | null): void {
        if (!this.parts) return;
        this.parts.message.textContent = text ?? '';
        this.parts.message.hidden = !text;
    }

    // -----------------------------------------------------------------------
    // View
    // -----------------------------------------------------------------------

    public get pageCount(): number {
        return this.slots.length;
    }

    /** The page in the middle of the viewer, or -1 without pages. */
    public get currentPage(): number {
        return this.current;
    }

    /** Scrolls so a page's top is at the top of the viewer. */
    public scrollToPage(page: number): void {
        const slot = this.slots[Math.max(0, Math.min(page, this.slots.length - 1))];
        if (!slot || !this.camera) return;
        this.camera.scrollTo(slot.top);
        this.updateCurrentPage();
    }

    public zoomIn(): void {
        this.run({ type: 'zoom-in' });
    }

    public zoomOut(): void {
        this.run({ type: 'zoom-out' });
    }

    /** Fits the pages (see the `fit` attribute). */
    public fit(): void {
        this.run({ type: 'fit' });
    }

    /**
     * Handles a shortcut (+ / - zoom, 0 fit, Shift + arrows pan, Page Up / Down, Home / End). Called for
     * keys pressed in the viewer; pages can also forward their own keydown events. A handled event is prevented.
     *
     * @return {boolean} True if the key was used.
     */
    public handleKey(event: KeyboardEvent): boolean {
        const command = event.defaultPrevented ? null : keyCommand(event);
        if (!command || (command.type === 'page' && this.slots.length < 2)) return false;
        this.run(command);
        event.preventDefault();
        return true;
    }

    // -----------------------------------------------------------------------
    // Internals: stage
    // -----------------------------------------------------------------------

    private createStage(container: HTMLDivElement): void {
        const stage = new Konva.Stage({
            container,
            ...this.stageSize(),
            draggable: true,
            dragDistance: 3, // a small slip is still a click
            dragBoundFunc: (pos) => this.camera?.clamp(pos) ?? pos,
        });
        stage.add(this.layer.add(this.shadow.node, this.content));
        const camera = new PageCamera(
            stage,
            () => this.contentSize,
            () => this.largestPage,
            () => this.numberAttribute('max-zoom', DEFAULT_MAX_ZOOM),
            () => (this.getAttribute('fit') === 'width' ? 'width' : 'page') satisfies FitMode,
        );
        this.camera = camera;

        stage.on('wheel', (event) => {
            const wheel = event.evt;
            wheel.preventDefault();
            // Ctrl + wheel (and trackpad pinch) zooms; the wheel scrolls through several pages
            if (wheel.ctrlKey || wheel.metaKey || this.slots.length < 2) {
                const step = this.numberAttribute('zoom-step', DEFAULT_ZOOM_STEP);
                const pointer = stage.getPointerPosition();
                if (pointer) camera.zoomBy(wheel.deltaY < 0 ? step : 1 / step, pointer);
                return;
            }
            const unit = wheel.deltaMode === WheelEvent.DOM_DELTA_LINE ? WHEEL_LINE
                : wheel.deltaMode === WheelEvent.DOM_DELTA_PAGE ? stage.height() : 1;
            const [dx, dy] = wheel.shiftKey && !wheel.deltaX ? [wheel.deltaY, 0] : [wheel.deltaX, wheel.deltaY];
            camera.pan(-dx * unit, -dy * unit);
            this.updateCurrentPage();
        });
        stage.on('dblclick dbltap', (event) => {
            if (event.target === stage) this.run({ type: 'fit' });
        });

        this.setCursor('grab');
        stage.on('dragstart', () => this.setCursor('grabbing'));
        stage.on('dragmove', () => this.updateCurrentPage());
        stage.on('dragend', () => this.setCursor('grab'));
    }

    private run(command: ViewerCommand): void {
        const camera = this.camera;
        if (!camera) return;
        const step = this.numberAttribute('zoom-step', DEFAULT_ZOOM_STEP);
        switch (command.type) {
            case 'zoom-in': camera.zoomBy(step); break;
            case 'zoom-out': camera.zoomBy(1 / step); break;
            case 'fit': camera.fit(); break;
            case 'pan': camera.pan(command.dx, command.dy); break;
            case 'page': {
                const last = this.slots.length - 1;
                const target = { previous: this.current - 1, next: this.current + 1, first: 0, last }[command.to];
                this.scrollToPage(target);
                return;
            }
        }
        this.updateCurrentPage();
    }

    // -----------------------------------------------------------------------
    // Internals: pages
    // -----------------------------------------------------------------------

    /** Stacks the pages, centered on the widest one, with a gap (or a divider) between them. */
    private layout(): void {
        const width = Math.max(0, ...this.slots.map((slot) => slot.width));
        const gap = width * PAGE_GAP_RATIO;
        const divider = width * DIVIDER_RATIO;

        let y = 0;
        for (const slot of this.slots) {
            if (slot.divider) y += divider;
            slot.x = (width - slot.width) / 2;
            slot.top = y;
            slot.group?.position({ x: slot.x, y: slot.top });
            y += slot.height + gap;
        }

        this.contentSize = { width, height: Math.max(0, y - gap) };
        this.largestPage = { width, height: Math.max(0, ...this.slots.map((slot) => slot.height)) };
        this.updateShadows();
    }

    /** Shadows under the rendered pages only: drawing thousands of them would be wasted work. */
    private updateShadows(): void {
        this.shadow.setRects(this.slots
            .filter((slot) => slot.group)
            .map(({ x, top, width, height }) => ({ x, y: top, width, height })));
    }

    /** Lays the pages out again (a page's real size differs), keeping the view on the same place of the current page. */
    private relayout(): void {
        const camera = this.camera;
        const anchor = this.slots[this.current];
        const offset = camera && anchor ? camera.topY() - anchor.top : 0;
        this.layout();
        if (camera && anchor) camera.scrollTo(anchor.top + offset);
    }

    /** Renders the current page and its neighbours (loading them if needed); un-renders the others. */
    private updateWindow(): void {
        const from = this.current - RENDERED_AROUND;
        const to = this.current + RENDERED_AROUND;
        this.slots.forEach((slot, index) => {
            const inWindow = index >= from && index <= to;
            if (!inWindow) this.unrender(slot);
            else if (slot.content || slot.error) this.renderSlot(slot, index);
            else this.load(slot, index);
        });
        this.updateShadows();
        this.layer.batchDraw();
    }

    /** Loads a page once; renders it if it's still near the view when it arrives. */
    private load(slot: PageSlot, index: number): void {
        const loader = this.loader;
        if (!loader || slot.loading) return;
        const generation = this.generation;

        slot.loading = loader(index).then((page) => {
            if (generation !== this.generation) return;
            slot.content = page;
            const divider = !!page.divider && index > 0;
            if (page.image.width !== slot.width || page.image.height !== slot.height || divider !== slot.divider) {
                slot.width = page.image.width;
                slot.height = page.image.height;
                slot.divider = divider;
                this.relayout();
            }
            this.updateWindow();
            if (index === this.current) this.updateIndicator();
        }, (error: unknown) => {
            if (generation !== this.generation) return;
            slot.error = pageError(index, error);
            this.updateWindow();
        }).finally(() => {
            if (generation === this.generation) slot.loading = undefined;
        });
    }

    /** Creates a loaded page's nodes (divider, image, then its shapes), or a failed page's notice. */
    private renderSlot(slot: PageSlot, index: number): void {
        if (slot.group) return;
        if (!slot.content) {
            if (slot.error) this.content.add(slot.group = this.errorNode(slot, slot.error));
            return;
        }
        const { image, shapes = [], divider } = slot.content;
        const group = new Konva.Group({ x: slot.x, y: slot.top });
        if (divider && slot.divider) group.add(this.dividerNode(divider, slot));
        group.add(new Konva.Image({ image, width: image.width, height: image.height, listening: false }));

        for (const shape of shapes) {
            const node = createShapeNode(shape);
            node.on('click tap', () => {
                this.dispatchEvent(new CustomEvent<ShapeClickDetail>('shape-click', {
                    detail: { shape, page: index },
                    bubbles: true,
                }));
            });
            node.on('mouseenter', () => this.setCursor('pointer'));
            node.on('mouseleave', () => this.setCursor('grab'));
            group.add(node);
        }

        this.content.add(group);
        slot.group = group;
    }

    /**
     * The divider above a page, in the space left for it: the end of the part above, a dashed line
     * across the column, and the start of this page's part.
     */
    private dividerNode({ end, start }: { end: string; start: string }, slot: PageSlot): Konva.Group {
        const width = this.contentSize.width;
        const height = width * DIVIDER_RATIO;
        const fontSize = width * DIVIDER_FONT_RATIO;
        const color = getComputedStyle(this).getPropertyValue('--bs-secondary-color').trim() || '#6c757d';
        const text = (value: string, y: number, bold: boolean): Konva.Text => new Konva.Text({
            text: value, x: 0, y, width, align: 'center', fontSize, fill: color,
            fontStyle: bold ? 'bold' : 'normal', fontFamily: getComputedStyle(this).fontFamily, listening: false,
        });

        // In the group's coordinates: above the page (negative y), across the whole column
        const group = new Konva.Group({ x: -slot.x, y: -height, listening: false });
        group.add(
            text(end, height * 0.18, false),
            new Konva.Line({
                points: [width * 0.05, height / 2, width * 0.95, height / 2],
                stroke: color, strokeWidth: 1, dash: [6, 4], strokeScaleEnabled: false,
            }),
            text(start, height * 0.62, true),
        );
        return group;
    }

    /** In place of a page that couldn't be loaded: a blank page with the reason. */
    private errorNode({ x, top, width, height }: PageSlot, reason: string): Konva.Group {
        return new Konva.Group({ x, y: top, listening: false }).add(
            new Konva.Rect({ width, height, fill: '#f8f9fa' }),
            new Konva.Text({
                text: `The scan couldn't be loaded\n${reason}`, y: height / 2, width, align: 'center',
                fontSize: width * 0.03, lineHeight: 1.6, fill: '#6c757d',
            }),
        );
    }

    /** Removes a page's nodes; its content stays, to render it again without reloading. */
    private unrender(slot: PageSlot): void {
        slot.group?.destroy();
        slot.group = undefined;
    }

    /** Finds the page in the middle of the viewer; when it changes, renders around it and announces it. */
    private updateCurrentPage(): void {
        const centerY = this.camera?.centerY ?? 0;
        let page = this.slots.length ? 0 : -1;
        this.slots.forEach((slot, index) => {
            if (slot.top <= centerY) page = index;
        });
        if (page === this.current) return;
        this.current = page;
        this.updateWindow();

        this.updateIndicator();
        this.dispatchEvent(new CustomEvent<PageChangeDetail>('page-change', {
            detail: { page, count: this.slots.length },
            bubbles: true,
        }));
    }

    /** The current page's label (or "Page 3 / 12") in the indicator; hidden with a single page. */
    private updateIndicator(): void {
        if (!this.parts) return;
        const label = this.slots[this.current]?.content?.label;
        this.parts.pageIndicator.hidden = this.slots.length < 2 && !label;
        this.parts.pageIndicator.textContent = label ?? `Page ${this.current + 1} / ${this.slots.length}`;
    }

    private stageSize(): { width: number; height: number } {
        return { width: this.parts?.stage.clientWidth ?? 0, height: this.parts?.stage.clientHeight ?? 0 };
    }

    private setCursor(cursor: string): void {
        if (this.parts) this.parts.stage.style.cursor = cursor;
    }

    private numberAttribute(name: string, fallback: number): number {
        return Number(this.getAttribute(name)) || fallback;
    }
}