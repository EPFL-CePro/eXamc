import DataTable, { type Api } from 'datatables.net-dt';
import {getLayoutElementsSeparator} from "@examc/helpers/datatables.ts";
import type {DataTableColumn} from "@examc/types/datatables.ts";

import 'datatables.net-dt/css/dataTables.dataTables.min.css';


// The values come from imported files: rendered as text, never as HTML
function textColumn(data: string): DataTableColumn {
    return { data, orderable: true, render: DataTable.render.text(), defaultContent: "" };
}

export function initPrepStudentsTable(options: {
    tableElement: HTMLTableElement;
    apiUrl: string;
}): Api {
    const { tableElement, apiUrl } = options;

    return new DataTable(tableElement, {
        serverSide: true,
        processing: true,
        ajax: {
            url: apiUrl,
            type: "GET",
        },
        layout: {
            bottomStart: [
                "pageLength",
                getLayoutElementsSeparator(),
                "info"
            ]
        },
        columns: [
            textColumn("copy_no"),
            textColumn("sciper"),
            textColumn("last_name"),
            textColumn("first_name"),
            textColumn("email"),
            textColumn("section"),
            textColumn("room"),
            textColumn("seat"),
        ],
        pageLength: 25,
        scrollY: "65vh",
        order: [[0, "asc"]],
    });
}
