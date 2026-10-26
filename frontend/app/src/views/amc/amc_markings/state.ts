import type { SearchableDropdown } from '@examc/helpers/searchable-dropdown/index.ts';

interface State {
    /** True while a marking run is streaming, so repeated clicks are ignored. */
    markingRunning: boolean;
    /** Student pickers of the manual association dialog, disposed before it is rebuilt. */
    studentPickers: SearchableDropdown[];
}

/** Single shared state object: modules mutate its fields (an exported `let` can't be reassigned by importers). */
export const state: State = {
    markingRunning: false,
    studentPickers: [],
};