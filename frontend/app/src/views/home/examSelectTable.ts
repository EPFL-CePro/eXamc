import DataTable from 'datatables.net-dt';

export function initExamSelectTable(options: {
    tableElement: HTMLTableElement;
    apiUrl: string;
}) {
    const { tableElement, apiUrl } = options;

    new DataTable(tableElement, {
        serverSide: true,
        processing: true,
        ajax: {
            url: apiUrl,
            type: "GET",
        },
        columns: [
            { data: "exam", orderable: true },
            { data: "date", orderable: true, width: "10rem" },
            { data: "role", orderable: false, width: "10rem" },
            { data: "modules", orderable: false, width: "10rem" },
            { data: "review", orderable: false, width: "10rem" },
            { data: "actions", orderable: false },
        ],
        order: [[1, "desc"]],
    });
}