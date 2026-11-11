/**
 * `<examc-page-viewer>`: importing this module registers the element.
 * See PageViewerElement for its attributes, slots, methods and events.
 */
import { PageViewerElement } from './page-viewer-element.ts';
import type { PageChangeDetail, ShapeClickDetail } from './types.ts';

export { PageViewerElement };
export type { PageChangeDetail, PageLoader, PageShape, ShapeClickDetail, ViewerPage } from './types.ts';

declare global {
    interface HTMLElementTagNameMap {
        'examc-page-viewer': PageViewerElement;
    }
    interface HTMLElementEventMap {
        /** A shape of an `<examc-page-viewer>` was clicked (not when the pages were dragged). */
        'shape-click': CustomEvent<ShapeClickDetail>;
        /** The page in the middle of an `<examc-page-viewer>` changed. */
        'page-change': CustomEvent<PageChangeDetail>;
    }
}

if (!customElements.get('examc-page-viewer')) customElements.define('examc-page-viewer', PageViewerElement);