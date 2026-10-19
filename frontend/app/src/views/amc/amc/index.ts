import { byId, requireData } from '@examc/helpers/dom.ts';
import { openLogFile } from './logs';
import { manageTabs } from '@examc/helpers/tabs';

document.addEventListener('DOMContentLoaded', () => {
    // Not rendered when the user isn't allowed or the exam has no AMC project yet.
    const root = byId<HTMLDivElement>('amc-page');

    manageTabs({ tabId: root.dataset.currentTab ?? '' });

    const logFileUrl = requireData(root, 'logFileUrl');
    const csrfToken = requireData(root, 'csrfToken');
    console.log('Log file URL:', logFileUrl);
    byId('btn-view-log-file').addEventListener('click', () => void openLogFile({ url: logFileUrl, csrfToken }));
});