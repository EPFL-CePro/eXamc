import 'datatables.net-bs5/css';

import DataTable from 'datatables.net-bs5';

/**
 * Initializes the exam select table and last user connected after the DOM has loaded.
 */
document.addEventListener("DOMContentLoaded", () => {
    const csvgenTableElement = document.querySelector<HTMLTableElement>("#datatable");
    const fileInput = document.querySelector<HTMLInputElement>('#excel_file');

    if (!csvgenTableElement || !fileInput) return;

    new DataTable(csvgenTableElement, {
        paging: false,
    });

    fileInput.addEventListener('change', () => {
        const label = fileInput.parentElement?.querySelector<HTMLLabelElement>('.custom-file');
        if (!label) return;

        label.textContent = fileInput.files?.[0]?.name ?? '';
        label.classList.add('selected');
    });
});


