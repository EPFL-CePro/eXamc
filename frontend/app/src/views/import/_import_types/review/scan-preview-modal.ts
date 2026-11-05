import { ExamcModal } from "@examc/modals/base";

/** Shows one unrecognized scan full size. Built when opened, removed once closed. */
export class ScanPreviewModal extends ExamcModal {
    public constructor(options: { imageUrl: string; title: string }) {
        super(ExamcModal.createElement({
            extraDialogClass: 'modal-xl modal-dialog-centered',
            noFooter: true,
            bodyContent: `<div class="modal-body text-center">${ScanPreviewModal.imageHtml(options)}</div>`,
        }));

        this.setTitle(options.title);
    }

    /**
     * The image's HTML, built through the DOM: the browser escapes the URL and the title,
     * so they're never parsed as markup.
     */
    private static imageHtml({ imageUrl, title }: { imageUrl: string; title: string }): string {
        const image = document.createElement('img');
        image.className = 'img-fluid';
        image.style.maxHeight = '80vh';
        image.src = imageUrl;
        image.alt = title;
        return image.outerHTML;
    }
}