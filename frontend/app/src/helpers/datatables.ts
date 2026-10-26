import DataTable from 'datatables.net-bs5';


/**
 * Common setup for DataTables.
 */
export function setupDatatables(): void {
    // make all column header right-aligned, regardless of data type
    DataTable.type('num', 'className', 'dt-body-right');
    DataTable.type('num-fmt', 'className', 'dt-body-right');
    DataTable.type('date', 'className', 'dt-body-right');
}
