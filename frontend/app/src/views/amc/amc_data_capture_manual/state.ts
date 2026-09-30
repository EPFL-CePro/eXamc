import type { Api } from 'datatables.net-dt';

import type { ScanView, Zone } from './types.ts';

interface State {
    table: Api | null;
    currentRow: HTMLTableRowElement | null;
    view: ScanView | null;
    zones: Zone[];
    /** Incremented on every load, so responses for a page the user already left are ignored. */
    loadToken: number;
}

/** Single shared state object: modules mutate its fields (an exported `let` can't be reassigned by importers). */
export const state: State = {
    table: null,
    currentRow: null,
    view: null,
    zones: [],
    loadToken: 0,
};