import DataTable, { type Api } from 'datatables.net-dt';
import 'datatables.net-dt/css/dataTables.dataTables.css';

import 'datatables.net-buttons-dt';
import 'datatables.net-select-dt';


import { getModal } from '@examc/helpers/modals.ts';
import { type ExamcEditor } from '@examc/types/editor';
import { setAjaxInfoModalLocked } from '@examc/helpers/ajax-info-modal.ts';
import { initEditor, getEditorContent } from "@examc/editor/index.ts";
import {byId, csrfToken, icon, requireData, sleep} from "@examc/helpers/dom.ts";
import {setupDatatables} from "@examc/helpers/datatables.ts";


// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CellValue = string | number | null;
type StudentRow = Record<string, CellValue>;

interface SendDataResponse {
    data?: StudentRow[];
    email_subject?: string;
    email_text?: string;
}

interface AnnotateStartResponse {
    status_url: string;
}

interface AnnotateStatusResponse {
    status: string; // "queued" | "running" | "done" | anything else = failed
    progress?: string;
    error?: string;
}

type SendResultResponse = [sent: number, notSent: number, details: string[]];

interface SelectedStudent {
    id: CellValue;
    copy: CellValue;
    email: CellValue;
}

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

async function post(url: string, body: FormData | Record<string, string>): Promise<Response> {
    const formData = body instanceof FormData ? body : new FormData();
    if (!(body instanceof FormData)) {
        for (const [key, value] of Object.entries(body)) formData.append(key, value);
    }
    if (!formData.has('csrfmiddlewaretoken')) formData.append('csrfmiddlewaretoken', csrfToken());

    const response = await fetch(url, { method: 'POST', body: formData, credentials: 'same-origin' });
    if (!response.ok) throw new Error(`HTTP ${response.status} on ${url}`);
    return response;
}

/** Parses a JSON body, also handling views that return a JSON-encoded string. */
async function readJson<T>(response: Response): Promise<T> {
    const data: unknown = await response.json();
    return (typeof data === 'string' ? JSON.parse(data) : data) as T;
}

async function postJson<T>(url: string, body: FormData | Record<string, string>): Promise<T> {
    return readJson<T>(await post(url, body));
}

async function getJson<T>(url: string): Promise<T> {
    const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`HTTP ${response.status} on ${url}`);
    return readJson<T>(response);
}

// ---------------------------------------------------------------------------
// Page elements and URLs
// ---------------------------------------------------------------------------

const root = byId('amc-results');
const urls = {
    generateResults: requireData(root, 'generateResultsUrl'),
    annotate: requireData(root, 'annotateUrl'),
    sendData: requireData(root, 'sendDataUrl'),
    send: requireData(root, 'sendUrl'),
};

const infoMessage = byId('ajax_info_modal_msg');
const infoModalElement = byId('ajax_info_modal');

const sendDialogElement = byId('send-annotated-papers-dialog');
const sendDialog = getModal({ type: 'local', element: sendDialogElement });
const sendForm = byId<HTMLFormElement>('form-send-annotated-papers');
const sendAlert = byId('send_annotated_alert');
const subjectInput = byId<HTMLInputElement>('email-subject');
const emailBodyEl = byId<HTMLTextAreaElement>('email-body');
let emailBodyEditor: ExamcEditor;

const emailColumnSelect = byId<HTMLSelectElement>('email-column');
const sendTableElement = byId<HTMLTableElement>('send-annotated-papers-table');

function showInfo(...content: (Node | string)[]): void {
    infoMessage.replaceChildren(...content);
    getModal({ type: 'local', element: infoModalElement }).show();
}

// ---------------------------------------------------------------------------
// Generate results
// ---------------------------------------------------------------------------

async function generateResults(button: HTMLButtonElement): Promise<void> {
    button.disabled = true;
    try {
        await post(urls.generateResults, {});
        window.location.reload();
    } catch (error) {
        console.error(error);
        showInfo('Failed to generate results.');
        button.disabled = false;
    }
}

// ---------------------------------------------------------------------------
// Annotate papers
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_FAILURES = 5;

async function annotate(): Promise<void> {
    showInfo("Generating annotated papers could take some time. We'll update this message when files are ready!");
    setAjaxInfoModalLocked(true);

    const singleFile = byId<HTMLInputElement>('annotate_one_all_student').checked;
    const withGradingScheme =
        document.querySelector<HTMLInputElement>('#annotate_with_grading_scheme')?.checked ?? false;

    let statusUrl: string;
    try {
        ({ status_url: statusUrl } = await postJson<AnnotateStartResponse>(urls.annotate, {
            single_file: singleFile ? '1' : '0',
            add_grading_scheme_report: String(withGradingScheme),
        }));
    } catch (error) {
        console.error(error);
        setAjaxInfoModalLocked(false);
        infoMessage.textContent = 'Failed to start annotation job.';
        return;
    }

    await pollAnnotateJob(statusUrl);
}

async function pollAnnotateJob(statusUrl: string): Promise<void> {
    let failures = 0;

    for (;;) {
        await sleep(POLL_INTERVAL_MS);

        let job: AnnotateStatusResponse;
        try {
            job = await getJson<AnnotateStatusResponse>(statusUrl);
            failures = 0;
        } catch (error) {
            console.error(error);
            if (++failures >= MAX_POLL_FAILURES) {
                setAjaxInfoModalLocked(false);
                infoMessage.textContent =
                    'Lost contact with the server while annotating. Reload the page later to check the result.';
                return;
            }
            continue;
        }

        if (job.status === 'queued' || job.status === 'running') {
            infoMessage.textContent = job.progress || 'Still working…';
            continue;
        }

        setAjaxInfoModalLocked(false);
        infoMessage.textContent = job.status === 'done'
            ? (job.progress ? `Done! ${job.progress}` : 'Done!')
            : `Annotation failed: ${job.error || 'unknown error'}`;
        return;
    }
}

// ---------------------------------------------------------------------------
// Email body
// ---------------------------------------------------------------------------

let pendingEmail: { subject: string; body: string } | null = null;

sendDialogElement.addEventListener('shown.bs.modal', async () => {
    emailBodyEditor = await initEditor({ target: emailBodyEl });

    if (pendingEmail) {
        subjectInput.value = pendingEmail.subject;

        pendingEmail = null;

    }

    // The table was built while the dialog was hidden, so its column widths need recalculating.
    sendTable?.columns.adjust();
});

// ---------------------------------------------------------------------------
// Students table
// ---------------------------------------------------------------------------

let sendTable: Api<StudentRow> | null = null;
let sendRows: StudentRow[] = [];

function renderCell(key: string, value: CellValue, row: StudentRow): HTMLTableCellElement {
    const td = document.createElement('td');

    if (key.includes('date')) {
        td.textContent = typeof value === 'number' ? new Date(value * 1000).toLocaleString() : '';
    } else if (key === 'status') {
        if (value === 1) {
            td.append(icon('fa-solid fa-thumbs-up fa-l', 'green'));
        } else if (value !== 0) {
            td.append(icon('fa-solid fa-triangle-exclamation fa-l', 'red', String(row['error'] ?? '')));
        }
    } else {
        td.textContent = value === null ? '' : String(value);
    }

    return td;
}

function buildSendTable(rows: StudentRow[]): void {
    if (DataTable.isDataTable(sendTableElement)) return;

    sendTable = null;
    sendRows = rows;

    const head = byId('send-annotated-papers-table-thead');
    const body = byId('send-annotated-papers-table-tbody');
    const keys = rows[0] ? Object.keys(rows[0]).filter((key) => key !== 'error') : [];

    head.replaceChildren(
        document.createElement('th'),
        ...keys.map((key) => {
            const th = document.createElement('th');
            th.textContent = key;
            return th;
        }),
    );

    body.replaceChildren(
        ...rows.map((row) => {
            const tr = document.createElement('tr');
            tr.append(document.createElement('td'), ...keys.map((key) => renderCell(key, row[key] ?? null, row)));
            return tr;
        }),
    );

    // avoid reinitializing the table
    if (DataTable.isDataTable(sendTableElement)) return;

    setupDatatables();

    sendTable = new DataTable(sendTableElement, {
        scrollY: '25vh',
        paging: false,
        select: {
            style: 'multi',
            selector: 'td',
            items: 'row',
        },
        columnDefs: [
            {
                targets: 0,
                orderable: false,
                searchable: false,
                render: DataTable.render.select(), // renders the checkbox
            },
        ],
        layout: {
            topEnd: 'search',
            bottomStart: 'info',
            bottomEnd: null,
        }
    });
}

function selectedStudents(): SelectedStudent[] {
    if (!sendTable) return [];
    const emailColumn = emailColumnSelect.value;
    const indexes = sendTable.rows({ selected: true }).indexes().toArray() as number[];

    return indexes.flatMap((index) => {
        const row = sendRows[index];
        if (!row) return [];
        // Assumes the first two data columns are the student id and copy number; adjust if needed.
        const values = Object.entries(row).filter(([key]) => key !== 'error').map(([, value]) => value);
        return [{ id: values[0] ?? null, copy: values[1] ?? null, email: row[emailColumn] ?? null }];
    });
}

// ---------------------------------------------------------------------------
// Send annotated papers
// ---------------------------------------------------------------------------
async function openSendDialog(): Promise<void> {
    try {
        const data = await postJson<SendDataResponse>(urls.sendData, {});
        buildSendTable(data.data ?? []);
        pendingEmail = { subject: data.email_subject ?? '', body: data.email_text ?? '' };
        sendDialog.show();
    } catch (error) {
        console.warn(error);
        showInfo('Failed to load the students list.');
    }
}

async function sendAnnotatedPapers(): Promise<void> {
    const subject = subjectInput.value.trim();
    const editorContent = getEditorContent({ editor: emailBodyEditor, format: "markdown" });
    const bodyIsEmpty = editorContent.trim() === '';

    if (bodyIsEmpty || subject === '') {
        sendAlert.style.visibility = 'visible';
        return;
    }

    sendAlert.style.visibility = 'hidden';

    // Includes the csrf token, email-column, email-subject and the synced email-body textarea.
    const formData = new FormData(sendForm);
    formData.set('selected-students', JSON.stringify(selectedStudents()));
    formData.set('email-body', editorContent);

    showInfo(
        "Sending annotated papers by email could take some time. A dialog will display when it's finished, "
        + 'and the results will also be visible in the send annotated papers modal!',
    );

    try {
        const [sent, notSent, details] = await postJson<SendResultResponse>(urls.send, formData);

        const list = document.createElement('ul');
        list.append(...details.map((detail) => {
            const item = document.createElement('li');
            item.textContent = detail;
            return item;
        }));

        showInfo(
            `${sent} emails sent, ${notSent} not sent!`,
            document.createElement('br'),
            document.createElement('br'),
            list,
        );
        sendDialog.hide();
    } catch (error) {
        console.error(error);
        showInfo('Failed to send the annotated papers.');
    }
}

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    const generateButton = byId<HTMLButtonElement>('generate-results-btn');
    generateButton.addEventListener('click', () => void generateResults(generateButton));

    byId('annotate-btn').addEventListener('click', annotate);
    document.getElementById('open-send-dialog-btn')?.addEventListener('click', openSendDialog);
    byId('send-annotated-papers-btn').addEventListener('click', sendAnnotatedPapers);
});