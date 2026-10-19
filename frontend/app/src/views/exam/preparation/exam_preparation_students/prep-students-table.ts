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

// A student without seat (in yellow) must get one before the final generation
function hasNoSeat(row: PrepStudentRow): boolean {
    return !row.needs_correction && !row.seat;
}

// Summary on the right of the tool bar, e.g. "232 students · 2 to correct · 1 without seat"
function updateSummary(rows: PrepStudentRow[], toCorrect: number, withoutSeat: number, summary: HTMLElement | null): void {
    if (!summary) return;

    const parts = [rows.length === 1 ? "1 student" : `${rows.length} students`];
    if (toCorrect) parts.push(`⚠ ${toCorrect} to correct`);
    if (withoutSeat) parts.push(`⚠ ${withoutSeat} without seat`);
    summary.textContent = parts.join(" · ");
}

// Banner above the table: students whose SCIPER was not found in the EPFL directory (red), without seat (yellow)
function updateToCorrectBanner(table: Api, banner: HTMLElement | null, summary: HTMLElement | null): void {
    const rows = table.rows().data().toArray() as PrepStudentRow[];
    const toCorrect = rows.filter((row) => row.needs_correction).length;
    const withoutSeat = rows.filter(hasNoSeat).length;
    updateSummary(rows, toCorrect, withoutSeat, summary);
    if (!banner) return;
    const lines = [];
    if (toCorrect) {
        lines.push(toCorrect === 1
            ? "1 student (in red) has a SCIPER not found in the EPFL directory: correct it with the pencil button."
            : `${toCorrect} students (in red) have a SCIPER not found in the EPFL directory: correct them with the `
              + "pencil button.");
    }
    if (withoutSeat) {
        lines.push(withoutSeat === 1
            ? "1 student (in yellow) has no seat: give one with the pencil button or Assign rooms and seats."
            : `${withoutSeat} students (in yellow) have no seat: give them one with Assign rooms and seats `
              + "or the pencil button.");
    }
    if (lines.length) lines.push("The final files cannot be generated before.");

    banner.hidden = lines.length === 0;
    // Red when a SCIPER is to correct, else yellow
    banner.classList.toggle("alert-danger", toCorrect > 0);
    banner.classList.toggle("alert-warning", toCorrect === 0);
    banner.replaceChildren(...lines.map((line) => {
        const div = document.createElement("div");
        div.textContent = line;
        return div;
    }));
}

export function initPrepStudentsTable(options: {
    tableElement: HTMLTableElement;
    apiUrl: string;
    toCorrectBanner?: HTMLElement | null;
    summary?: HTMLElement | null;
}): Api {
    const { tableElement, apiUrl, toCorrectBanner = null, summary = null } = options;
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
            } else if (hasNoSeat(data as PrepStudentRow)) {
                (row as HTMLElement).classList.add("table-warning");
            }
        },
        scrollY: "65vh",
        order: [[0, "asc"]],
    });

    table.on("xhr", () => {
        // After the "xhr" event, the rows are not drawn yet
        window.setTimeout(() => updateToCorrectBanner(table, toCorrectBanner, summary));
    });
    return table;
}
