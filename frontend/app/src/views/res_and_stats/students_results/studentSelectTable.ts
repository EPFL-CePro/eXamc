import DataTable from 'datatables.net-dt';
import type {DataTableColumn} from "@examc/types/datatables.ts";

type PresenceResponse = {
    student: number;
    present: boolean;
    updated: boolean;
    present_students: number;
    task_id: string | null;
    html: string;
};


/**
 * One column per <th data-scale-pk>, reading row.scales[pk]
 * */
function scaleColumns(tableElement: HTMLTableElement): DataTableColumn[] {
    const headers = tableElement.querySelectorAll<HTMLTableCellElement>("thead th[data-scale-pk]");

    return Array.from(headers, (th) => ({
        data: `scales.${th.dataset.scalePk}`,
        orderable: false,
        searchable: false,
        defaultContent: "",
    }));
}

export function initStudentsTable(options: {
    tableElement: HTMLTableElement;
    apiUrl: string;
    csrfToken: string;
    onPresenceChange?: (response: PresenceResponse) => void;
}): void {
    const { tableElement, apiUrl, csrfToken, onPresenceChange } = options;

    const columns: DataTableColumn[] = [
        { data: "copy_no", orderable: true },
        { data: "sciper", orderable: true },
        { data: "name", orderable: true },
        { data: "present", orderable: true, searchable: false },
        { data: "points", orderable: true },
        ...scaleColumns(tableElement),
    ];

    const headerCount = tableElement.tHead?.rows[0]?.cells.length ?? 0;
    if (headerCount !== columns.length) {
        throw new Error(
            `#${tableElement.id}: ${headerCount} header cells but ${columns.length} columns. ` +
            "Do all scale <th> have data-scale-pk?"
        );
    }

    const table = new DataTable(tableElement, {
        serverSide: true,
        processing: true,
        ajax: {
            url: apiUrl,
            type: "GET"
        },
        columns,
        pageLength: 25,
        scrollY: '75vh',
        order: [[0, "asc"]],
    });

    /**
     * Manages presence on-off toggles
     */
    tableElement.addEventListener("click", async (event: PointerEvent): Promise<void> => {
        const button = (event.target as Element).closest<HTMLButtonElement>(".presence-toggle button[data-present]");
        const toggle = button?.closest<HTMLElement>(".presence-toggle");
        const cell = toggle?.closest("td");
        if (!button || !toggle?.dataset.url || !cell) return;

        const response = await fetch(toggle.dataset.url, {
            method: "PATCH",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
            body: JSON.stringify({ present: button.dataset.present === "1" }),
        });

        if (!response.ok) {
            console.error("Could not update presence", response.status, await response.text());
            alert("Could not update presence.");
            return;
        }

        const data: PresenceResponse = await response.json();
        table.cell(cell).data(data.html); // swap in the server-rendered toggle
        onPresenceChange?.(data);
    });
}