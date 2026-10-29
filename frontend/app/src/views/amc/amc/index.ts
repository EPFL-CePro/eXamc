import { byId, requireData } from '@examc/helpers/dom.ts';
import { openLogFile } from './logs';
import { manageTabs } from '@examc/helpers/tabs';
import { UploadAmcProjectModal } from './upload-amc-project-modal';

document.addEventListener('DOMContentLoaded', () => {
    // Not rendered when the user isn't allowed or the exam has no AMC project yet.
    const root = byId<HTMLDivElement>('amc-page');
    const csrfToken = requireData(root, 'csrfToken');
    const logFileUrl = requireData(root, 'logFileUrl');

    manageTabs();

    // upload AMC project
    const uploadAmcProjectBtn = byId("btn-upload-amc-project");
    uploadAmcProjectBtn.addEventListener("click", () => {
        new UploadAmcProjectModal({
            uploadUrl: requireData(uploadAmcProjectBtn, "uploadAmcProjectUrl"),
            csrfToken
        }).show();
    });

    // open logs
    document.querySelector('#btn-view-log-file')?.addEventListener('click', () => {
        void openLogFile({ url: logFileUrl, csrfToken });
    });
});