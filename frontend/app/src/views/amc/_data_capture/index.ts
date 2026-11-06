import { byId, requireData } from '@examc/helpers/dom.ts';

import { readJsonArray } from './data.ts';
import { initAutomaticImport } from './automatic/import.ts';
import type { ReviewScanCopy } from './automatic/types.ts';
import { initManualCapture } from './manual/index.ts';
import { initReports } from './reports/reports.ts';
import type { MissingPagesCopy, OverwrittenPage } from './reports/types.ts';

document.addEventListener('DOMContentLoaded', () => {
    const root = byId('amc-data-capture');

    initAutomaticImport({
        examPk: requireData(root, 'examPk'),
        zipImportUrl: requireData(root, 'zipImportUrl'),
        importAllUrl: requireData(root, 'importAllUrl'),
        importPagesUrl: requireData(root, 'importPagesUrl'),
        scans: readJsonArray<ReviewScanCopy>('json-scans-list'),
    });

    initReports({
        unrecognizedUrl: requireData(root, 'unrecognizedUrl'),
        missingPages: readJsonArray<MissingPagesCopy>('json-missing-pages'),
        overwrittenPages: readJsonArray<OverwrittenPage>('json-overwritten-pages'),
    });

    void initManualCapture(root);
});
