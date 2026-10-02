import { byId } from '@examc/helpers/dom.ts';
import { parseJson, postText } from '@examc/helpers/http.ts';
import { getModal, withLoading } from '@examc/helpers/modals.ts';
import { CsvError, readCsv, writeCsv } from './students-table/csv.ts';
import { ModuleUninitialized } from './errors.ts';
import { state } from './state.ts';
import { buildStudentsTable, studentsTableRows } from './students-table/index.ts';
import type { EditFileResponse, StudentsUrls } from './types.ts';

let urls: StudentsUrls | null = null;

/** Sets the API endpoints. Called by index.ts once the DOM has loaded. */
export function initStudents(endpoints: StudentsUrls): void {
    urls = endpoints;
}

/**
 * Shows a students list error in the page, or hides the error box.
 *
 * @param {string | null} message - The error, or null to hide the box.
 */
function showStudentsListError(message: string | null): void {
    const errorBox = byId('csv-import-error');
    errorBox.hidden = message === null;
    errorBox.textContent = message ?? '';
}

/**
 * Handles the answer of the views that change the students list: 'ok', or an error message.
 *
 * @param {string} result - The response text.
 */
function applyResult(result: string): void {
    if (!urls) throw new ModuleUninitialized('students.ts', 'initStudents');

    if (result === 'ok') {
        showStudentsListError(null);
        window.location.reload();
        return;
    }

    showStudentsListError(result);
}

/**
 * Uploads the CSV file selected in the students list form.
 *
 * @param {HTMLFormElement} form - The form holding the file input and CSRF token.
 */
export async function uploadStudentsFile(form: HTMLFormElement): Promise<void> {
    if (!urls) throw new ModuleUninitialized('students.ts', 'initStudents');
    const url = urls.updateFile;

    try {
        // Multipart upload; the form already contains the CSRF token.
        const result = await withLoading(async () => {
            const response = await fetch(url, { method: 'POST', body: new FormData(form), credentials: 'same-origin' });
            if (!response.ok) throw new Error(`Students file upload failed: ${response.status}`);
            return response.text();
        });
        applyResult(result);
    } catch (error) {
        console.error(error);
    }
}

/**
 * Loads the students list and opens it in the edit dialog's table.
 * If the file is not a valid CSV, the error is shown in the page instead.
 */
export async function openEditStudentsListModal(): Promise<void> {
    if (!urls) throw new ModuleUninitialized('students.ts', 'initStudents');

    try {
        const file = parseJson<EditFileResponse>(await postText(urls.editFile, { filepath: 'students_list' }));
        if (!file) throw new Error('edit_amc_file returned no data');

        const [filepath, content] = file;
        const { header, rows, format } = readCsv(content); // throws CsvError if the file isn't a valid CSV
        state.studentsList = { filepath, header, format };

        showStudentsListError(null);
        buildStudentsTable(header, rows);
        byId('edit-students-list-modal-title').textContent = `Edit ${filepath.split('/').pop() ?? ''}`;
        getModal({ type: 'local', element: byId('edit-students-list-modal') }).show();
    } catch (error) {
        if (error instanceof CsvError) {
            showStudentsListError(`The students list can't be edited, it is not a valid CSV file. ${error.message}`);
            return;
        }
        console.error(error);
    }
}

/** Saves the students list edited in the dialog, written back as CSV in its original format. */
export async function saveStudentsListFile(): Promise<void> {
    if (!urls) throw new ModuleUninitialized('students.ts', 'initStudents');
    const list = state.studentsList;
    if (!list) return;

    const url = urls.saveFile;
    const payload = {
        data: writeCsv(list.header, studentsTableRows(), list.format),
        filepath: list.filepath,
        is_students_list: 'true',
    };

    try {
        const result = await withLoading(() => postText(url, payload));
        getModal({ type: 'local', element: byId('edit-students-list-modal') }).hide();
        applyResult(result);
    } catch (error) {
        console.error(error);
    }
}