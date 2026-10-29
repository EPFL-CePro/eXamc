import DataTable, { type Api } from 'datatables.net-bs5';
import 'datatables.net-bs5/css';

import { setupDatatables } from '@examc/helpers/datatables.ts';
import { byId, requireData } from '@examc/helpers/dom.ts';
import { parseJson } from '@examc/helpers/http.ts';

import { createByExamChart, createClosedEndedChart, createOpenChart } from './charts.ts';
import type { QuestionsStatsCharts } from './types.ts';
import { renderElToPdf } from '@examc/helpers/pdf.ts';
import { manageTabs } from '@examc/helpers/tabs.ts';
import { LoadingModal } from '@examc/modals/loading.ts';

/**
 * Creates a statistics table: all rows, no search, sorted by question.
 *
 * @param {HTMLTableElement} table - The table.
 * @return {Api<unknown>} The DataTable.
 */
function createStatsTable(table: HTMLTableElement): Api<unknown> {
    return new DataTable(table, {
        scrollY: '68vh',
        paging: false,
        searching: false,
        info: false,
        order: [[1, 'asc']]
    });
}


/**
 * "Show in pdf" links open the catalog in the dialog, searched for the question's code.
 *
 * @param {HTMLElement} modal - The dialog.
 * @param {string} catalogUrl - The catalog PDF's URL.
 */
function initCatalogDialog(modal: HTMLElement, catalogUrl: string): void {
    const viewer = modal.querySelector<HTMLElement>('[data-pdf-viewer]');
    modal.addEventListener('show.bs.modal', (event) => {
        const trigger = (event as Event & { relatedTarget?: HTMLElement }).relatedTarget;
        const code = trigger?.dataset['questionCode'] ?? '';

        const embed = document.createElement('embed');
        embed.type = 'application/pdf';
        embed.src = `${catalogUrl}#search=${encodeURIComponent(code)}&toolbar=0&navpanes=0&scrollbar=0`;
        embed.className = 'flex-grow-1 w-100';
        viewer?.replaceChildren(embed);
    });
}

/**
 * The PDF download buttons ([data-pdf-element]) export a part of the page.
 *
 * @param {HTMLElement} root - The page.
 */
function initPdfDownloads(root: HTMLElement): void {
    root.addEventListener('click', (event) => {
        const button = (event.target as Element).closest<HTMLElement>('[data-pdf-element]');
        if (!button) return;

        new LoadingModal(() => renderElToPdf({
            el: byId(requireData(button, 'pdfElement')),
            fileName: requireData(button, 'pdfFile'),
            title: requireData(button, 'pdfTitle'),
            orientation: 'l',
        })).result.catch((error: unknown) => console.error('Could not create the PDF', error));
    });
}

document.addEventListener('DOMContentLoaded', () => {
    // Not rendered when the user isn't allowed or there is no statistic.
    const root = byId('questions-statistics');

    manageTabs({ tabListSelector: "#questions-stats-tabs" });

    // Charts
    const charts = parseJson<QuestionsStatsCharts>(byId('questions-stats-charts').textContent);
    if (charts) {
        charts.mcq.forEach(createClosedEndedChart);
        charts.open.forEach((chart) => createOpenChart(chart, charts.presentStudents));
        charts.byExam.forEach(createByExamChart);
    }

    manageTabs({ tabListSelector: '#questions-statistics-pills-tab' });

    // Tables, measured again once their section or tab is shown (they may be created hidden)
    setupDatatables();

    const tables = Array.from(root.querySelectorAll<HTMLTableElement>('table[data-stats-table]')).map(createStatsTable);
    tables.forEach((table) => table.columns.adjust());

    initPdfDownloads(root);
    initCatalogDialog(byId('display-pdf-modal'), requireData(root, 'catalogUrl'));
});