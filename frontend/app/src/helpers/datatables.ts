import DataTable from 'datatables.net-dt';

/**
 * Returns a function that provides a reusable HTMLSpanElement as a separator.
 * The separator contains the "|" character as its content.
 *
 * @return {function(): HTMLSpanElement} A function that returns the pre-created separator span element.
 */
export function getLayoutElementsSeparator(): () => HTMLSpanElement {
    const separator = document.createElement('span');
    separator.innerText = "|";

    return function() {
        return separator;
    };
}

/**
 * Common setup for DataTables.
 */
export function setupDatatables(): void {
    // make all column header right-aligned, regardless of data type
    DataTable.type('num', 'className', 'dt-body-right');
    DataTable.type('num-fmt', 'className', 'dt-body-right');
    DataTable.type('date', 'className', 'dt-body-right');
}
