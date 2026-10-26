import { ExamcModal } from "@examc/modals/base";

interface PdfModalOptions {
    /** The modal's title. */
    title: string;
    /** The PDF's URL. */
    url: string;
    /** Opens the PDF on this page (1 for the first). */
    page?: number;
    /** Searches the PDF for this text, e.g. a question's code. Not supported by every browser's viewer. */
    search?: string;
}

/**
 * A modal showing a PDF in the browser's viewer. Built on the fly and removed once closed.
 *
 * @example
 * PdfModal.open({ title: "Catalog", url: catalogUrl, search: question.code });
 */
export class PdfModal extends ExamcModal {
    private constructor({ title, url, page, search }: PdfModalOptions) {
        super(ExamcModal.createElement({
            extraDialogClass: "modal-xl",
            bodyContent: `
                <div class="modal-body p-0">
                    <iframe class="d-block w-100 border-0" style="height: 80vh"></iframe>
                </div>`,
            noFooter: true,
        }));
        this.setTitle(title);

        // The viewer's options go in the URL's fragment: #page=2&search=Q1
        const fragment = new URLSearchParams();
        if (page) fragment.set("page", String(page));
        if (search) fragment.set("search", search);

        const iframe = this.element.querySelector("iframe")!;
        iframe.title = title;
        iframe.src = fragment.size ? `${url}#${fragment}` : url;
    }

    /** Opens a modal on a PDF. */
    public static open(options: PdfModalOptions): PdfModal {
        const modal = new PdfModal(options);
        modal.show();
        return modal;
    }
}