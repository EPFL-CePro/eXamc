import type { Api } from 'datatables.net-dt';

import type { QuestionFilter, ScanView, TypeFilter, Zone } from './types.ts';

interface State {
    table: Api<unknown> | null;
    currentRow: HTMLTableRowElement | null;
    view: ScanView | null;
    zones: Zone[];
    typeFilter: TypeFilter;
    questionFilter: QuestionFilter;
    /** Incremented on every load, so responses for a page the user already left are ignored. */
    loadToken: number;
}

/** Single shared state object: modules mutate its fields (an exported `let` can't be reassigned by importers). */
export const state: State = {
    table: null,
    currentRow: null,
    view: null,
    zones: [],
    typeFilter: 'all',
    questionFilter: { id: 0, name: 'All' },
    loadToken: 0,
};