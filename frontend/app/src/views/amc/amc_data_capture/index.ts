import './main.scss';

import { byId, requireData } from '@examc/helpers/dom.ts';

import { readJsonArray } from './data.ts';
import { initAutomaticImport } from './import.ts';
import { initReports } from './reports.ts';
import { initDiagnosis, navigateZooms } from './table.ts';
import type { MissingPagesCopy, OverwrittenPage, ReviewScanCopy } from './types.ts';
import { initZooms } from './zooms.ts';

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

    initZooms({
        zoomsUrl: requireData(root, 'zoomsUrl'),
        updateZoneUrl: requireData(root, 'updateZoneUrl'),
        onNavigate: navigateZooms,
    });

    // The diagnosis table is only rendered when there is captured data.
    const table = document.getElementById('table-copies-pages');
    if (table instanceof HTMLTableElement) initDiagnosis(table);
});