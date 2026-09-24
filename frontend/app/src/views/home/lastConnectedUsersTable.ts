import DataTable from 'datatables.net-dt';
import {getLayoutElementsSeparator} from "@examc/helpers/datatables.ts";

export function lastConnectedUsersTable(options: {
    tableElement: HTMLTableElement;
}) {
    const { tableElement } = options;

    new DataTable(tableElement, {
        scrollY: '18.1vh',
        layout: {
            topStart: function() {
                let title = document.createElement('h4');
                title.style.margin = "0";
                title.innerHTML = `<i class="fa-solid fa-clock-rotate-left dashboard-section-icon"></i>Users' last connection`;
                return title;
            },
            bottomStart: [
                "pageLength",
                getLayoutElementsSeparator(),
                "info"
            ]
        }
    });
}