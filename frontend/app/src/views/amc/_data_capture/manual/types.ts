/** A question state that needs attention. */
export type QuestionState = 'invalid' | 'empty';

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
    why?: string | null; // 'E' = invalid, 'V' = empty
    checked?: boolean;
}

/** A mark zone, as the update endpoint identifies it (the data of its shape in the viewer). */
export interface Zone {
    zoneid: number;
    corner: number;
}

/** Endpoints read from the root element's data attributes. */
export interface ScanUrls {
    scanUrl: string;
    marks: string;
    updateZone: string;
}