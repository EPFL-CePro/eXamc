/**
 * `<examc-resize-handle>`: importing this module registers the element.
 * See ResizeHandleElement for its attributes and events.
 */
import { ResizeHandleElement } from './resize-handle-element.ts';

export { ResizeHandleElement };

declare global {
    interface HTMLElementTagNameMap {
        'examc-resize-handle': ResizeHandleElement;
    }
    interface HTMLElementEventMap {
        /** An `<examc-resize-handle>` started resizing this element. */
        'resize-start': CustomEvent<null>;
        /** An `<examc-resize-handle>` finished resizing this element. */
        'resize-end': CustomEvent<null>;
    }
}

if (!customElements.get('examc-resize-handle')) customElements.define('examc-resize-handle', ResizeHandleElement);