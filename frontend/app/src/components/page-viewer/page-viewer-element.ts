import Konva from 'konva';

import type {} from '../resize-handle/index.ts'; // types only: its resize-start / resize-end events

import { keyCommand } from './keyboard.ts';
import { PageCamera } from './page-camera.ts';
import { PageShadow } from './page-shadow.ts';
import { createShapeNode } from './shapes.ts';
import { render, type ViewerParts } from './template.ts';
import type { PageShape, ShapeClickDetail, ViewerCommand } from './types.ts';

const DEFAULT_ZOOM_STEP = 1.25;
const DEFAULT_MAX_ZOOM = 8;

/**
 * `<examc-page-viewer>`: a page image with clickable shapes over it, zoom (wheel, keys, toolbar),
 * panning (drag, Shift + arrows) and a soft page shadow. It takes the size its element is given,
 * and uses the page's Bootstrap and Font Awesome.
 *
 * Attributes: `zoom-step` (default 1.25), `max-zoom` (relative to the whole page, default 8).
 * Children: `slot="toolbar"` (secondary toolbar, top left), `slot="help"` (extra `<li>` help lines).
 * Events: `shape-click` (detail: `{ shape }`). While an `<examc-resize-handle>` resizes it, the page
 * shadow tucks under the page.
 */
export class PageViewerElement extends HTMLElement {
    private parts: ViewerParts | null = null;
    private readonly resizeObserver = new ResizeObserver(() => this.camera?.resize(this.stageSize()));

    private readonly image = new Konva.Image({ image: undefined, listening: false });
    private readonly shadow = new PageShadow();
    private readonly shapes = new Konva.Group();
    private camera: PageCamera | null = null;

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

    /** Shows an image and fits it to the viewer; null removes it. */
    public setImage(image: HTMLImageElement | null): void {
        const size = { width: image?.width ?? 0, height: image?.height ?? 0 };
        this.image.image(image ?? undefined).size(size);
        this.shadow.setSize(size);
        this.camera?.fit();
    }

    /** Replaces the shapes drawn over the image. */
    public setShapes<T>(shapes: PageShape<T>[]): void {
        this.shapes.destroyChildren();
        for (const shape of shapes) {
            const node = createShapeNode(shape);
            node.on('click tap', () => {
                this.dispatchEvent(new CustomEvent<ShapeClickDetail>('shape-click', { detail: { shape }, bubbles: true }));
            });
            node.on('mouseenter', () => this.setCursor('pointer'));
            node.on('mouseleave', () => this.setCursor('grab'));
            this.shapes.add(node);
        }
    }

    /** Removes the image and its shapes. */
    public clear(): void {
        this.setShapes([]);
        this.setImage(null);
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

    public zoomIn(): void {
        this.run({ type: 'zoom-in' });
    }

    public zoomOut(): void {
        this.run({ type: 'zoom-out' });
    }

    /** Shows the whole page. */
    public fit(): void {
        this.run({ type: 'fit' });
    }

    /**
     * Handles a shortcut (+ / - zoom, 0 whole page, Shift + arrows pan). Called for keys pressed in the
     * viewer; pages can also forward their own keydown events. A handled event is prevented.
     *
     * @return {boolean} True if the key was used.
     */
    public handleKey(event: KeyboardEvent): boolean {
        const command = event.defaultPrevented ? null : keyCommand(event);
        if (!command) return false;
        this.run(command);
        event.preventDefault();
        return true;
    }

    // -----------------------------------------------------------------------
    // Internals
    // -----------------------------------------------------------------------

    private createStage(container: HTMLDivElement): void {
        const stage = new Konva.Stage({
            container,
            ...this.stageSize(),
            draggable: true,
            dragDistance: 3, // a small slip is still a click
            dragBoundFunc: (pos) => this.camera?.clamp(pos) ?? pos,
        });
        stage.add(new Konva.Layer().add(this.shadow.node, this.image, this.shapes));
        const camera = new PageCamera(stage, () => this.image.size(), () => this.numberAttribute('max-zoom', DEFAULT_MAX_ZOOM));
        this.camera = camera;

        stage.on('wheel', (event) => {
            event.evt.preventDefault();
            const step = this.numberAttribute('zoom-step', DEFAULT_ZOOM_STEP);
            const pointer = stage.getPointerPosition();
            if (pointer) camera.zoomBy(event.evt.deltaY < 0 ? step : 1 / step, pointer);
        });
        stage.on('dblclick dbltap', (event) => {
            if (event.target === stage || event.target === this.image) camera.fit();
        });

        this.setCursor('grab');
        stage.on('dragstart', () => this.setCursor('grabbing'));
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
        }
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