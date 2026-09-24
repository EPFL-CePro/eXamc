import DataTable from 'datatables.net-dt';
import {getLayoutElementsSeparator} from "@examc/helpers/datatables.ts";

export function initExamSelectTable(options: {
    tableElement: HTMLTableElement;
    apiUrl: string;
}) {
    const { tableElement, apiUrl } = options;

    new DataTable(tableElement, {
        serverSide: true,
        processing: true,
        scrollY: "45.5dvh",
        ajax: {
            url: apiUrl,
            type: "GET",
        },
        layout: {
            topStart: function() {
                let title = document.createElement('h4');
                title.style.margin = "0";
                title.innerHTML = `<i class="fa-solid fa-book-open"></i> My exams`;
                return title;
            },
            bottomStart: [
                "pageLength",
                getLayoutElementsSeparator(),
                "info"
            ]
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