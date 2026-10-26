import DataTable from 'datatables.net-bs5';
import 'datatables.net-bs5/css';

export function initTableMarkingDetails(options: { tableElement: HTMLTableElement }): void {
    const { tableElement } = options;

    new DataTable(tableElement, {
        paging: false,
        scrollCollapse: true,
        scrollY: "65vh",
        layout: {
            topEnd: null
        }
    });
}