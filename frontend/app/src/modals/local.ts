import type { ExamcModalOptions } from "@examc/types/modals";

import { ExamcModal } from "@examc/modals/base";

/** A modal already in the page's template. */
export class LocalModal extends ExamcModal {
    public constructor(element: HTMLElement, modalOptions?: ExamcModalOptions) {
        super(element, modalOptions);
    }
}