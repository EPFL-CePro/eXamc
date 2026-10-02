import type { Api } from 'datatables.net-dt';

import type { SearchableDropdown } from '@examc/helpers/searchable-dropdown/index.ts';
import type { StudentsListFile, StudentsListRow } from './types.ts';

interface State {
    /** The students list open in the edit dialog. */
    studentsList: StudentsListFile | null;
    /** The edit dialog's table, rebuilt each time the dialog opens (the columns may change). */
    studentsTable: Api<StudentsListRow> | null;
    /** True while a marking run is streaming, so repeated clicks are ignored. */
    markingRunning: boolean;
    /** Student pickers of the manual association dialog, disposed before it is rebuilt. */
    studentPickers: SearchableDropdown[];
}

/** Single shared state object: modules mutate its fields (an exported `let` can't be reassigned by importers). */
export const state: State = {
    studentsList: null,
    studentsTable: null,
    markingRunning: false,
    studentPickers: [],
};