import { byId } from '@examc/helpers/dom.ts';
import { parseJson, postText } from '@examc/helpers/http.ts';
import { LoadingModal } from '@examc/modals/loading.ts';

import { ModuleUninitialized } from './errors.ts';
import { StudentsListModal } from './students-list-modal.ts';
import { CsvError, readCsv, writeCsv } from './student-table-csv.ts';
import type { CsvFormat, EditFileResponse, StudentsListRow, StudentsUrls } from './types.ts';

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
 * Uploads the CSV file selected in the students list form, then reloads the page,
 * or shows the server's error in the page.
 *
 * @param {HTMLFormElement} form - The form holding the file input and CSRF token.
 */
export async function uploadStudentsFile(form: HTMLFormElement): Promise<void> {
    if (!urls) throw new ModuleUninitialized('students.ts', 'initStudents');
    const url = urls.updateFile;

    try {
        // Multipart upload; the form already contains the CSRF token.
        const result = await new LoadingModal(async () => {
            const response = await fetch(url, { method: 'POST', body: new FormData(form), credentials: 'same-origin' });
            if (!response.ok) throw new Error(`Students file upload failed: ${response.status}`);
            return response.text();
        }).result;

        if (result === 'ok') window.location.reload();
        else showStudentsListError(result);
    } catch (error) {
        console.error(error);
        showStudentsListError('The students list could not be uploaded. Please try again.');
    }
}

/**
 * Loads the students list and opens it in the edit dialog.
 * If the file can't be loaded or isn't a valid CSV, the error is shown in the page instead.
 */
export async function openEditStudentsListModal(): Promise<void> {
    if (!urls) throw new ModuleUninitialized('students.ts', 'initStudents');
    const url = urls.editFile;

    let file: EditFileResponse | null;
    try {
        file = parseJson<EditFileResponse>(
            await new LoadingModal(() => postText(url, { filepath: 'students_list' })).result,
        );
        if (!file) throw new Error('edit_amc_file returned no data');
    } catch (error) {
        console.error(error);
        showStudentsListError('The students list could not be loaded. Please try again.');
        return;
    }

    const [filepath, content] = file;
    let csv: ReturnType<typeof readCsv>;
    try {
        csv = readCsv(content);
    } catch (error) {
        if (!(error instanceof CsvError)) throw error;
        showStudentsListError(`The students list can't be edited, it is not a valid CSV file. ${error.message}`);
        return;
    }

    showStudentsListError(null);

    new StudentsListModal({
        title: `Edit ${filepath.split('/').pop() ?? ''}`,
        header: csv.header,
        rows: csv.rows,
        onSave: (rows) => saveStudentsList(filepath, csv.header, csv.format, rows),
    }).show();
}

/**
 * Saves the edited students list, written back as CSV in its original format, then reloads the page.
 *
 * @param {string} filepath - The file's path in the AMC project.
 * @param {string[]} header - The CSV header.
 * @param {CsvFormat} format - The format the file was read with.
 * @param {StudentsListRow[]} rows - The edited rows.
 * @throws {Error} With a message for the user, if the list could not be saved.
 */
async function saveStudentsList(
    filepath: string,
    header: string[],
    format: CsvFormat,
    rows: StudentsListRow[],
): Promise<void> {
    if (!urls) throw new ModuleUninitialized('students.ts', 'initStudents');

    let result: string;
    try {
        result = await postText(urls.saveFile, {
            data: writeCsv(header, rows, format),
            filepath,
            is_students_list: 'true',
        });
    } catch (error) {
        console.error(error);
        throw new Error('The students list could not be saved. Please try again.', { cause: error });
    }

    // The view answers 'ok', or an error message for the user.
    if (result !== 'ok') throw new Error(result);
    window.location.reload();
}