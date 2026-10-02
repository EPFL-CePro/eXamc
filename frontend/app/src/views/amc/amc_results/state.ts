import type { Api } from 'datatables.net-dt';

import type { ExamcEditor } from '@examc/types/editor';
import type { PendingEmail, StudentRow } from './types.ts';

interface State {
    sendTable: Api<StudentRow> | null;
    /** Rows of the send table, in table index order. */
    sendRows: StudentRow[];
    /** Email body editor, created the first time the send dialog is shown. */
    emailEditor: ExamcEditor | null;
    /** Default email waiting for the send dialog to be shown. */
    pendingEmail: PendingEmail | null;
}

/** Single shared state object: modules mutate its fields (an exported `let` can't be reassigned by importers). */
export const state: State = {
    sendTable: null,
    sendRows: [],
    emailEditor: null,
    pendingEmail: null,
};