export type TypeFilter = 'all' | 'invalid' | 'empty';

export interface QuestionFilter {
    id: number;
    name: string;
}

/** One row of the pages table, as returned by the API. */
export interface PageRow {
    copy: number | string;
    page: number | string;
    mse: number | null;
    timestamp_auto: number | null;
    timestamp_manual: number | null;
    sensitivity: number | null;
    questions_ids: string;
}

/** A question on a page, with its special state if any. */
export interface PageQuestion {
    id: number;
    name: string;
    state: 'invalid' | 'empty' | null;
}

/** One row of the pages table, as returned by the API. */
export interface PageRow {
    copy: number | string;
    page: number | string;
    mse: number | null;
    timestamp_auto: number | null;
    timestamp_manual: number | null;
    sensitivity: number | null;
    questions_ids: string;
    page_questions: PageQuestion[];
}

/** One corner of a mark zone, as returned by get_amc_marks_positions. */
export interface MarkPosition {
    zoneid: number;
    corner: number; // 1..4, sent in order for each zone
    x: number;
    y: number;
    manual?: number;
    black?: number;
    why?: string | null; // 'E' = invalid, 'V' = empty
    checked?: boolean;
}

export interface Point {
    x: number;
    y: number;
}

/** A mark zone scaled to canvas (CSS pixel) coordinates. */
export interface Zone {
    zoneid: number;
    corner: number;
    why: string;
    checked: boolean;
    points: [Point, Point, Point, Point];
    left: number;
    top: number;
    right: number;
    bottom: number;
}

/** The page currently shown on the canvas. */
export interface ScanView {
    copy: string;
    page: string;
    image: HTMLImageElement;
    marks: MarkPosition[];
}