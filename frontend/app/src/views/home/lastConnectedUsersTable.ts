import DataTable from 'datatables.net-dt';
import {getLayoutElementsSeparator, setupDatatables} from "@examc/helpers/datatables.ts";

export function lastConnectedUsersTable(options: {
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
        scrollY: '18.1vh',
        order: [[1, "desc"]],
        layout: {
            topStart: function() {
                const title = document.createElement('h4');
                title.style.margin = "0";
                title.innerHTML = `<i class="fa-solid fa-clock-rotate-left dashboard-section-icon"></i>Users' last connection`;

                return title;
            },
            bottomStart: [
                "pageLength",
                getLayoutElementsSeparator(),
                "info"
            ],
        },
        columns:[
            { data: "username", orderable: true },
            { data: "last_login", orderable: true }
        ],
        language:{
            emptyTable: "No login data available.",
        }
    });
}