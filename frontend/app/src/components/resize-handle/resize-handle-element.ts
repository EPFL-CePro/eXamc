import { hostClasses, template } from './template.ts';

/**
 * `<examc-resize-handle for="target-id">`: drag it to resize its target. Put it on any side of the
 * target; it works out from its position which way a drag grows it. The target's CSS min/max
 * width (or height) limit the size.
 *
 * Attributes: `for` (the target's id), `orientation` (`vertical`, default: a vertical bar that changes
 * the width; `horizontal`: a horizontal bar that changes the height).
 * Events, on the target: `resize-start` and `resize-end` (both bubble).
 */
export class ResizeHandleElement extends HTMLElement {
    public connectedCallback(): void {
        if (this.childElementCount) return; // already built
        const vertical = this.getAttribute('orientation') !== 'horizontal';

        this.classList.add(...hostClasses(vertical));
        this.style.cursor = vertical ? 'col-resize' : 'row-resize';
        this.style.touchAction = 'none'; // a finger drag resizes instead of scrolling
        this.setAttribute('role', 'separator');
        this.setAttribute('aria-orientation', vertical ? 'vertical' : 'horizontal');
        this.title ||= 'Drag to resize';
        this.innerHTML = template(vertical);

        this.addEventListener('pointerdown', (event) => this.startDrag(event, vertical));
    }

    private startDrag(event: PointerEvent, vertical: boolean): void {
        const target = document.getElementById(this.getAttribute('for') ?? '');
        if (!target) return;
        event.preventDefault();
        this.setPointerCapture(event.pointerId);

        // A handle after the target (right / below) grows it when dragged away; before it, the other way
        const handle = this.getBoundingClientRect();
        const box = target.getBoundingClientRect();
        const after = vertical ? handle.left >= box.right - 1 : handle.top >= box.bottom - 1;
        const sign = after ? 1 : -1;
        const start = vertical ? event.clientX : event.clientY;
        const startSize = vertical ? target.offsetWidth : target.offsetHeight;

        target.dispatchEvent(new CustomEvent('resize-start', { bubbles: true }));

        // At most one size change per frame, however often the pointer moves
        let position: number | null = null;
        let frame = 0;
        const apply = (): void => {
            frame = 0;
            if (position === null) return;
            const size = `${startSize + sign * (position - start)}px`;
            if (vertical) target.style.width = size;
            else target.style.height = size;
            target.style.aspectRatio = 'auto'; // the size is now the user's
        };
        const onMove = (move: PointerEvent): void => {
            position = vertical ? move.clientX : move.clientY;
            frame ||= requestAnimationFrame(apply);
        };
        const onEnd = (): void => {
            this.removeEventListener('pointermove', onMove);
            this.removeEventListener('pointerup', onEnd);
            this.removeEventListener('pointercancel', onEnd);
            cancelAnimationFrame(frame);
            apply();
            target.dispatchEvent(new CustomEvent('resize-end', { bubbles: true }));
        };
        this.addEventListener('pointermove', onMove);
        this.addEventListener('pointerup', onEnd);
        this.addEventListener('pointercancel', onEnd); // e.g. the browser took over a touch
    }
}