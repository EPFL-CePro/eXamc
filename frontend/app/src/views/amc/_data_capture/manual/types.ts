/** A question state that needs attention. */
export type QuestionState = 'invalid' | 'empty';

/** AMC's "why" code of a flagged question: E = erreur (invalid answer), V = vide (no answer). */
export type QuestionStateWhy = 'E' | 'V';

/** A question on a page, with its special state if any. */
export interface PageQuestion {
    id: number;
    name: string;
    state: QuestionState | null;
}

/** One row of the pages table, as returned by the API. */
export interface PageRow {
    copy: number | string;
    page: number | string;
    mse: number | null;
    sensitivity: number | null;
    timestamp_manual: number | null; // Unix seconds
    page_questions: PageQuestion[];
    states: QuestionState[];
}

/** A copy/page pair, as sent to the AMC endpoints. */
export interface PagePosition {
    copy: string;
    page: string;
}

/** One corner of a mark zone, as returned by get_amc_marks_positions. */
export interface MarkPosition {
    zoneid: number;
    corner: number; // 1..4
    x: number; // scan image pixels
    y: number;
    why?: QuestionStateWhy | null;
    checked?: boolean;
}

/** A mark zone, as the update endpoint identifies it (the data of its shape in the viewer). */
export interface Zone {
    zoneid: number;
    corner: number;
}

/** A page of the whole capture (all copies, copy after copy), as returned by the sequence endpoint. */
export interface SequencePage {
    copy: string;
    page: string;
    /** Position of its copy among all copies, from 0. */
    copy_index: number;
    /** Position of the page in its copy, from 0. */
    page_index: number;
    /** Number of pages of its copy. */
    page_count: number;
}

/** A slice of the sequence endpoint (?offset=&limit=). */
export interface SequenceSlice {
    total: number;
    copy_count: number;
    pages: SequencePage[];
}

/** Endpoints read from the root element's data attributes. */
export interface ScanUrls {
    scanUrl: string;
    marks: string;
    updateZone: string;
    /** A slice of all the pages, copy after copy (?offset=&limit=). */
    sequence: string;
    /** Index of a copy/page in that sequence (?copy=&page=). */
    locate: string;
}