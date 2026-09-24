import 'vite/modulepreload-polyfill';

import {initUserSelectTable} from "./userSelectTable";


/**
 * Initializes the exam select table after the DOM has loaded.
 */
document.addEventListener("DOMContentLoaded", () => {
    const tableElement = document.querySelector<HTMLTableElement>("#impersonation-users-table");
    if (!tableElement) return;

    const apiUrl = tableElement.dataset.apiUrl;

    if (!apiUrl) {
        console.error("Exam table missing data-api-url attribute");
        return;
    }

    initUserSelectTable({ tableElement, apiUrl });
});

/*
$(function () {
        const $table = $('#impersonation-users-table');
        $table.DataTable({
            serverSide: true,
            ajax: $table.data('url'),
            paging: true,
            pageLength: 50,
            lengthChange: false,
            info: false,
            order: [],
            columns: [
                { data: 'username' },
                { data: 'name' },
                { data: 'email' },
                { data: 'last_login' },
                { data: 'action', orderable: false, searchable: false },
            ],
            language: {
                zeroRecords: 'No active non-superuser account is available.',
            },
        });
    });
 */