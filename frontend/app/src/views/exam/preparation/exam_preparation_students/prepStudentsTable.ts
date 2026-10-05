import DataTable, { type Api } from 'datatables.net-dt';
import type {DataTableColumn} from "@examc/types/datatables.ts";

import 'datatables.net-dt/css/dataTables.dataTables.min.css';

export type PrepStudentRow = {
    id: number;
    copy_no: number;
    sciper: number;
    last_name: string;
    first_name: string;
    email: string | null;
    section: string | null;
    room: string | null;
    seat: string;
    needs_correction: boolean;
};


// The values come from imported files: rendered as text, never as HTML
function textColumn(data: string): DataTableColumn {
    return { data, orderable: true, render: DataTable.render.text(), defaultContent: "" };
}

// Banner above the table: number of students whose SCIPER was not found in the EPFL directory
function updateToCorrectBanner(table: Api, banner: HTMLElement | null): void {
    if (!banner) return;

    const count = (table.rows().data().toArray() as PrepStudentRow[]).filter((row) => row.needs_correction).length;
    banner.hidden = count === 0;
    banner.textContent = count === 1
        ? "1 student (in red) has a SCIPER not found in the EPFL directory: correct it with the pencil button. "
          + "The final files cannot be generated before."
        : `${count} students (in red) have a SCIPER not found in the EPFL directory: correct them with the `
          + "pencil button. The final files cannot be generated before.";
}

export function initPrepStudentsTable(options: {
    tableElement: HTMLTableElement;
    apiUrl: string;
    toCorrectBanner?: HTMLElement | null;
}): Api {
    const { tableElement, apiUrl, toCorrectBanner = null } = options;
    const editable = tableElement.dataset.editable === "true";

    // At most ~550 students per exam: all loaded at once, searched and sorted in the browser, no pages
    const table = new DataTable(tableElement, {
        ajax: {
            url: apiUrl,
            type: "GET",
        },
        paging: false,
        scrollCollapse: true,
        columns: [
            // Numbers from the database: sorted as numbers, no HTML possible
            { data: "copy_no" },
            { data: "sciper" },
            textColumn("last_name"),
            textColumn("first_name"),
            textColumn("email"),
            textColumn("section"),
            textColumn("room"),
            textColumn("seat"),
            {
                data: "id",
                orderable: false,
                searchable: false,
                width: "2rem",
                render: (id: number) => editable
                    ? `<button type="button" class="btn btn-link btn-sm p-0 prep-student-edit" data-id="${Number(id)}" `
                      + `title="Edit this student" aria-label="Edit this student"><i class="fa-solid fa-pen"></i></button>`
                    : "",
            },
        ],
        createdRow: (row: Node, data: object) => {
            if ((data as PrepStudentRow).needs_correction) {
                (row as HTMLElement).classList.add("table-danger");
            }
        },
        scrollY: "65vh",
        order: [[0, "asc"]],
    });

    table.on("xhr", () => {
        // After the "xhr" event, the rows are not drawn yet
        window.setTimeout(() => updateToCorrectBanner(table, toCorrectBanner));
    });
    return table;
}
