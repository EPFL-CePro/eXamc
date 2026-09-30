import DataTable from 'datatables.net-dt';
import 'datatables.net-dt/css/dataTables.dataTables.min.css';
import {setupDatatables} from "@examc/helpers/datatables.ts";

export function initUserSelectTable(options: {
    tableElement: HTMLTableElement;
    apiUrl: string;
}): void {
    const { tableElement, apiUrl } = options;

    setupDatatables();

    new DataTable(tableElement, {
        serverSide: true,
        processing: true,
        ajax: {
            url: apiUrl,
            type: "GET",
        },
        columns: [
            { data: "username" },
            { data: "name" },
            { data: "email" },
            { data: "last_login", render: DataTable.render.datetime() },
            { data: "action" },
        ],
        pageLength: 25,
        scrollY: '75vh',
        order: [[3, "desc"]],
    });
}