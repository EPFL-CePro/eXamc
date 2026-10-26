import { byId } from '@examc/helpers/dom.ts';
import { parseJson, postText } from '@examc/helpers/http.ts';
import { createSearchableDropdown, type SearchableDropdownChoice } from '@examc/helpers/searchable-dropdown/index.ts';
import { LoadingModal, LocalModal } from '@examc/modals';
import { ModuleUninitialized } from './errors.ts';
import { ManualAssociationModal } from './manual-association-modal.ts';
import { state } from './state.ts';
import type {
    AssociationRow,
    AssociationUrls,
    AutoAssociationResponse,
    ManualAssociationPayload,
    SetManualAssociationResponse,
    StudentRow,
} from './types.ts';

/** What AMC stores in `manual` to mark a sheet as associated with no student. */
const NO_STUDENT = 'NONE';

/** Value of the "Select..." choice: sent to remove the student from a sheet. */
const NO_STUDENT_CHOICE = '0';

let urls: AssociationUrls | null = null;

/** The manual association dialog, while it's open. */
let manualAssociationModal: ManualAssociationModal | null = null;

/** Sets the API endpoints. Called by index.ts once the DOM has loaded. */
export function initAssociation(endpoints: AssociationUrls): void {
    urls = endpoints;
}

/**
 * Shows a message in the page's info modal.
 *
 * @param {string} message - The message.
 */
function showInfo(message: string): void {
    byId('ajax-info-modal-msg').innerText = message;
    new LocalModal(byId('ajax-info-modal')).show();
}

/**
 * Adds a tab to a URL, as query parameter and hash.
 *
 * @param {string} url - The URL.
 * @param {string} tab - The tab id.
 * @return {string} The URL with the tab.
 */
function withTab(url: string, tab: string): string {
    const target = new URL(url, window.location.origin);
    target.searchParams.set('tab', tab);
    target.hash = tab;
    return target.toString();
}

/** Associates papers with students automatically, using the selected primary key. */
export async function runAutomaticAssociation(): Promise<void> {
    if (!urls) throw new ModuleUninitialized('association.ts', 'initAssociation');

    const primaryKey = byId<HTMLSelectElement>('automatic-assoc-primary-key').value;
    if (!primaryKey) {
        showInfo('Choose a primary key from the students list first.');
        return;
    }

    const url = urls.automatic;
    try {
        const data = parseJson<AutoAssociationResponse>(
            await new LoadingModal(() => postText(url, { assoc_primary_key: primaryKey })).result
        );
        if (data?.ok && data.redirect) {
            window.location.href = withTab(data.redirect, 'marking-tab');
        } else if (!data?.ok) {
            showInfo(data?.error ?? 'Unknown error');
        }
    } catch (error) {
        console.error(error);
        alert('Request failed.');
    }
}

/**
 * Text of a nullable value.
 *
 * @param {number | string | null | undefined} value - The value.
 * @return {string} Its text, '' for null.
 */
const toText = (value: number | string | null | undefined): string => (value == null ? '' : String(value));

/**
 * Identifies a sheet within the table.
 *
 * @param {AssociationRow} data - The sheet.
 * @return {string} "sheet:copy".
 */
const sheetKey = (data: AssociationRow): string => `${toText(data.student)}:${toText(data.copy ?? 0)}`;

/**
 * The student a sheet is associated with: the manual association if any, else the automatic one.
 * A manual 'NONE' means no student, whatever `auto` says.
 *
 * @param {AssociationRow} data - The sheet.
 * @return {string} The student code, '' if none.
 */
function effectiveStudent(data: AssociationRow): string {
    const manual = toText(data.manual);
    if (manual === NO_STUDENT) return '';
    return manual || toText(data.auto);
}

/**
 * Creates a text cell.
 *
 * @param {string} text - The cell's text.
 * @param {string} [className] - Classes of the cell.
 * @return {HTMLTableCellElement} The cell.
 */
function textCell(text: string, className?: string): HTMLTableCellElement {
    const td = document.createElement('td');
    td.textContent = text;
    if (className) td.className = className;
    return td;
}

/**
 * Creates the status cell of a sheet.
 *
 * @param {boolean} associated - Whether the sheet has a student.
 * @return {HTMLTableCellElement} The cell.
 */
function statusCell(associated: boolean): HTMLTableCellElement {
    const badge = document.createElement('span');
    badge.className = associated ? 'badge bg-success' : 'badge bg-danger';
    badge.innerHTML = associated
        ? '<span class="fa-solid fa-check"></span>' 
        : '<span class="fa-solid fa-xmark"></span>';

    const td = document.createElement('td');
    td.className = "text-center";
    td.append(badge);
    return td;
}

/**
 * Saves a manual association (or removes the student for "Select..."), then redraws the rows from
 * the database: associating a student also unlinks them from their previous sheet, so other rows
 * can change too, and a failed save puts the picker back to what is actually stored.
 *
 * @param {AssociationRow} sheet - The answer sheet.
 * @param {string} studentId - The selected student code, or NO_STUDENT_CHOICE.
 */
async function setManualAssociation(sheet: AssociationRow, studentId: string): Promise<void> {
    if (!urls) throw new ModuleUninitialized('association.ts', 'initAssociation');

    try {
        const response = parseJson<SetManualAssociationResponse>(await postText(urls.setManual, {
            copy_nr: toText(sheet.student),
            copy: toText(sheet.copy ?? 0),
            student_id: studentId,
        }));
        manualAssociationModal?.showError(response?.ok ? null : (response?.error ?? 'The association could not be saved.'));
    } catch (error) {
        console.error(error);
        manualAssociationModal?.showError('The association could not be saved.');
    }

    try {
        const payload = await loadManualAssociationData();

        // The dialog may have been closed while the data was loading.
        const modal = manualAssociationModal;
        if (!modal) return;

        renderManualAssociationRows(modal, payload, { refreshImages: false });
        focusSheetPicker(modal, sheetKey(sheet));
    } catch (error) {
        console.error(error);
        manualAssociationModal?.showError('The associations could not be reloaded. Close and reopen the dialog.');
    }
}

/**
 * Builds one row of the manual association table.
 *
 * @param {AssociationRow} data - The answer sheet.
 * @param {SearchableDropdownChoice[]} choices - The student choices, shared by every row.
 * @param {Map<string, HTMLImageElement>} images - Images to reuse, by sheet, instead of reloading them.
 * @return {HTMLTableRowElement} The row.
 */
function buildRow(
    data: AssociationRow,
    choices: SearchableDropdownChoice[],
    images: Map<string, HTMLImageElement>,
): HTMLTableRowElement {
    const auto = toText(data.auto);
    const manual = toText(data.manual);
    const student = effectiveStudent(data);

    const row = document.createElement('tr');
    row.dataset['sheet'] = sheetKey(data);
    row.append(
        textCell(toText(data.student)),
        textCell(auto),
        manual === NO_STUDENT ? textCell('None', 'text-muted fst-italic') : textCell(manual),
        statusCell(student !== ''),
    );

    const imageCell = document.createElement('td');
    const reused = images.get(sheetKey(data));
    const reusedUrl = reused?.getAttribute('src') ?? reused?.dataset['src'];
    const image = reused && reusedUrl === data.image_path ? reused : document.createElement('img');
    if (image !== reused) image.dataset['src'] = data.image_path; // loaded once its row is shown
    image.loading = 'lazy';
    image.alt = `Sheet ${toText(data.student)}`;
    imageCell.append(image);
    row.append(imageCell);

    const known = choices.some((choice) => choice.value === student);
    const picker = createSearchableDropdown({
        choices,
        selected: student || NO_STUDENT_CHOICE,
        // A code that isn't in the students list still shows, instead of a blank button.
        placeholder: known ? '' : `${student} (not in the students list)`,
        onChange: (studentId) => void setManualAssociation(data, studentId),
        searchLabel: 'Search students',
    });
    state.studentPickers.push(picker);

    const pickerCell = document.createElement('td');
    pickerCell.append(picker.element);
    row.append(pickerCell);

    if (!student) row.classList.add('missing-association');
    return row;
}

/** Releases the student pickers of the rows about to be replaced. */
function disposeStudentPickers(): void {
    for (const picker of state.studentPickers) picker.dispose();
    state.studentPickers = [];
}

/**
 * Turns the students list into picker choices, with "Select..." first, as in the original.
 *
 * @param {StudentRow[]} students - The students, without the header row.
 * @return {SearchableDropdownChoice[]} The choices.
 */
function studentChoices(students: StudentRow[]): SearchableDropdownChoice[] {
    return [
        { value: NO_STUDENT_CHOICE, label: 'Select...' },
        ...students.map(([id, first, second]) => ({ value: String(id), label: `${first} - ${second}`, keywords: String(id) })),
    ];
}

/**
 * Collects the scan images currently shown, by sheet.
 *
 * @param {HTMLTableRowElement[]} rows - The table's rows, all pages included.
 * @return {Map<string, HTMLImageElement>} The images.
 */
function currentImages(rows: HTMLTableRowElement[]): Map<string, HTMLImageElement> {
    const images = new Map<string, HTMLImageElement>();
    for (const row of rows) {
        const image = row.querySelector('img');
        if (image && row.dataset['sheet']) images.set(row.dataset['sheet'], image);
    }
    return images;
}

/**
 * Focuses a sheet's picker after a redraw, so keyboard users stay where they were.
 *
 * @param {ManualAssociationModal} modal - The dialog.
 * @param {string} key - The sheet key.
 */
function focusSheetPicker(modal: ManualAssociationModal, key: string): void {
    const row = modal.rowNodes().find((candidate) => candidate.dataset['sheet'] === key);
    if (!row) return;

    modal.showRow(row);
    row.querySelector<HTMLElement>('.dropdown-toggle')?.focus();
}

/**
 * Loads the associations and students from the server.
 *
 * @return {Promise<ManualAssociationPayload>} The answer sheets and students.
 */
async function loadManualAssociationData(): Promise<ManualAssociationPayload> {
    if (!urls) throw new ModuleUninitialized('association.ts', 'initAssociation');

    const payload = parseJson<ManualAssociationPayload>(await postText(urls.manualData, {}));
    if (!payload) throw new Error('amc_manual_association_data returned no data');
    return payload;
}

/**
 * Redraws the dialog's rows from the loaded data.
 *
 * @param {ManualAssociationModal} modal - The dialog.
 * @param {ManualAssociationPayload} payload - The answer sheets and students.
 * @param {{ refreshImages?: boolean }} [options] - refreshImages: false keeps the scan images already loaded.
 */
function renderManualAssociationRows(
    modal: ManualAssociationModal,
    payload: ManualAssociationPayload,
    options?: { refreshImages?: boolean },
): void {
    const { refreshImages = true } = options ?? {};
    const images = refreshImages ? new Map<string, HTMLImageElement>() : currentImages(modal.rowNodes());
    const choices = studentChoices(payload.data_students ?? []);

    disposeStudentPickers();
    modal.setRows((payload.data_assoc ?? []).map((data) => buildRow(data, choices, images)));
}

/** Loads the answer sheets and students, then opens the manual association dialog. */
export async function openManualAssociationDialog(): Promise<void> {
    try {
        const payload = await loadManualAssociationData();

        const modal = new ManualAssociationModal(() => {
            disposeStudentPickers();
            manualAssociationModal = null;
        });
        manualAssociationModal = modal;

        renderManualAssociationRows(modal, payload);
        modal.show();
    } catch (error) {
        console.error(error);
        showInfo('The manual association data could not be loaded.');
    }
}