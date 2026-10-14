import { byId, requireData } from '@examc/helpers/dom.ts';
import { openLogFile } from './logs';
import { showInitialTab } from './tabs';

document.addEventListener('DOMContentLoaded', () => {
    // Not rendered when the user isn't allowed or the exam has no AMC project yet.
    const root = byId<HTMLDivElement>('amc-page');
    const tabList = byId<HTMLUListElement>('amc-tabs');
    const tabs = [...tabList.querySelectorAll<HTMLButtonElement>('[data-bs-toggle="pill"]')];

    // Keep the selected tab in the URL, without adding history entries or scrolling to the anchor.
    for (const tab of tabs) {
        tab.addEventListener('shown.bs.tab', () => history.replaceState(null, '', `#${tab.id}`));
    }
    showInitialTab(tabs, root.dataset.currentTab ?? '');

    const logFileUrl = requireData(root, 'logFileUrl');
    const csrfToken = requireData(root, 'csrfToken');
    console.log('Log file URL:', logFileUrl);
    byId('btn-view-log-file').addEventListener('click', () => void openLogFile({ url: logFileUrl, csrfToken }));
});