import { ExamcModal } from "@examc/modals";

let count = 0;

/**
 * Uploads an AMC project (.zip of its directory). The form is posted by the browser: the upload's result is the
 * page the view answers with. While uploading, the dialog can't be closed. Use UploadAmcProjectModal.open().
 */
export class UploadAmcProjectModal extends ExamcModal {
    private uploading = false;

    public constructor(options: { uploadUrl: string; csrfToken: string }) {
        const { uploadUrl, csrfToken } = options;

        const helpId = `amc-project-zip-help-${++count}`;
        super(ExamcModal.createElement({
            titleContent: "Upload AMC project",
            extraDialogClass: "modal-lg",
            bodyContent: `
                <form method="post" enctype="multipart/form-data">
                    <input type="hidden" name="csrfmiddlewaretoken">
                    <div class="modal-body">
                        <label class="form-label w-100">AMC project (.zip file)
                            <input type="file" class="form-control mt-1" name="amc_project_zip_file"
                                   accept=".zip,application/zip" required aria-describedby="${helpId}">
                        </label>
                        <div class="form-text" id="${helpId}">The .zip file of the whole AMC project directory.</div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-primary">
                            <i class="fa-solid fa-cloud-arrow-up me-1" aria-hidden="true"></i>Start upload
                        </button>
                    </div>
                </form>`,
        }));

        const form = this.element.querySelector("form")!;
        form.action = uploadUrl;
        form.querySelector<HTMLInputElement>('input[name="csrfmiddlewaretoken"]')!.value = csrfToken;

        // The browser checks the required file before this event: the upload starts, until the page changes
        form.addEventListener("submit", () => {
            this.uploading = true;
            form.querySelectorAll("button").forEach((button) => { button.disabled = true; });
            form.querySelector('button[type="submit"]')!.innerHTML =
                '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>Uploading...';
        });

        // Closing would not stop the upload, only hide it: refused while uploading
        this.element.addEventListener("hide.bs.modal", (event) => {
            if (this.uploading) event.preventDefault();
        });
    }
}