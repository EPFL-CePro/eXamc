import { byId } from '@examc/helpers/dom.ts';
import { parseJson, postText } from '@examc/helpers/http.ts';
import { getModal, withLoading } from '@examc/helpers/modals.ts';
import { createSearchableDropdown, type SearchableDropdownChoice } from '@examc/helpers/searchable-dropdown/index.ts';
import { ModuleUninitialized } from './errors.ts';
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
    byId('ajax_info_modal_msg').innerText = message;
    getModal({ type: 'local', element: byId('ajax_info_modal') }).show();
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
            await withLoading(() => postText(url, { assoc_primary_key: primaryKey })),
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
 * Shows an error in the manual association dialog, or hides it.
 *
 * @param {string | null} message - The error, or null to hide it.
 */
function showAssociationError(message: string | null): void {
    const box = byId('manual-association-error');
    box.hidden = message === null;
    box.textContent = message ?? '';
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
        showAssociationError(response?.ok ? null : (response?.error ?? 'The association could not be saved.'));
    } catch (error) {
        console.error(error);
        showAssociationError('The association could not be saved.');
    }

    try {
        await rebuildManualAssociationRows({ refreshImages: false });
        focusSheetPicker(sheetKey(sheet));
    } catch (error) {
        console.error(error);
        showAssociationError('The associations could not be reloaded. Close and reopen the dialog.');
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
    );

    const imageCell = document.createElement('td');
    const reused = images.get(sheetKey(data));
    const image = reused?.getAttribute('src') === data.image_path ? reused : document.createElement('img');
    image.src = data.image_path;
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
 * @param {HTMLTableSectionElement} tbody - The table body.
 * @return {Map<string, HTMLImageElement>} The images.
 */
function currentImages(tbody: HTMLTableSectionElement): Map<string, HTMLImageElement> {
    const images = new Map<string, HTMLImageElement>();
    for (const row of Array.from(tbody.rows)) {
        const image = row.querySelector('img');
        if (image && row.dataset['sheet']) images.set(row.dataset['sheet'], image);
    }
    return images;
}

/**
 * Focuses a sheet's picker after a redraw, so keyboard users stay where they were.
 *
 * @param {string} key - The sheet key.
 */
function focusSheetPicker(key: string): void {
    byId('manual-association-table-tbody')
        .querySelector<HTMLElement>(`tr[data-sheet="${CSS.escape(key)}"] .dropdown-toggle`)
        ?.focus();
}

/**
 * Loads the associations and students from the server and redraws the table from them.
 * The current rows stay in place if loading fails.
 *
 * @param {{ refreshImages?: boolean }} [options] - refreshImages: false keeps the scan images already loaded.
 */
async function rebuildManualAssociationRows(options?: { refreshImages?: boolean }): Promise<void> {
    if (!urls) throw new ModuleUninitialized('association.ts', 'initAssociation');
    const { refreshImages = true } = options ?? {};

    const payload = parseJson<ManualAssociationPayload>(await postText(urls.manualData, {}));
    if (!payload) throw new Error('amc_manual_association_data returned no data');

    const rows = payload.data_assoc ?? [];
    const students = payload.data_students ?? [];

    const tbody = byId<HTMLTableSectionElement>('manual-association-table-tbody');
    const images = refreshImages ? new Map<string, HTMLImageElement>() : currentImages(tbody);
    const choices = studentChoices(students);

    disposeStudentPickers();
    tbody.replaceChildren(...rows.map((data) => buildRow(data, choices, images)));
}

/** Loads the answer sheets and students, then opens the manual association dialog. */
export async function openManualAssociationDialog(): Promise<void> {
    try {
        await rebuildManualAssociationRows();
        showAssociationError(null);
        getModal({ type: 'local', element: byId('manual-association-modal') }).show();
    } catch (error) {
        console.error(error);
        showInfo('The manual association data could not be loaded.');
    }
}