/**
 * `<examc-page-viewer>`: importing this module registers the element.
 * See PageViewerElement for its attributes, slots, methods and events.
 */
import { PageViewerElement } from './page-viewer-element.ts';
import type { ShapeClickDetail } from './types.ts';

export { PageViewerElement };
export type { PageShape, ShapeClickDetail } from './types.ts';

declare global {
    interface HTMLElementTagNameMap {
        'examc-page-viewer': PageViewerElement;
    }
    interface HTMLElementEventMap {
        /** A shape of an `<examc-page-viewer>` was clicked (not when the page was dragged). */
        'shape-click': CustomEvent<ShapeClickDetail>;
    }
}

if (!customElements.get('examc-page-viewer')) customElements.define('examc-page-viewer', PageViewerElement);