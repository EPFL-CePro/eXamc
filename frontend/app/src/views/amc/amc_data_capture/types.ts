/** One scan file of a copy in the review app (scans_list_json). */
export interface ReviewScanPage {
    page: string;
    path: string;
}

/** A copy and its scan files in the review app (scans_list_json). */
export interface ReviewScanCopy {
    copy: string | number;
    pages: ReviewScanPage[];
}

/** A copy with pages missing from the data capture (missing_pages). */
export interface MissingPagesCopy {
    copy_no: string | number;
    missing_pages: (string | number)[];
}

/** A page whose capture was overwritten (overwritten_pages). */
export interface OverwrittenPage {
    student: string | number;
    page: string | number;
    timestamp_auto: number | null; // Unix seconds
}

/** A scan AMC could not match to a copy/page (get_unrecognized_pages). */
export interface UnrecognizedPage {
    filename: string;
    filepath: string;
}

/** One box zoom of a page (get_amc_zooms). */
export interface Zoom {
    zoneid: number;
    imagedata: string; // base64 PNG
    bvalue: number;
    checked: boolean;
}

/** Response of the "import from review" endpoints. */
export interface JobStarted {
    status_url: string;
}

/** Response of a job status URL. */
export interface JobStatus {
    status: string; // 'queued' | 'running' | 'done' | anything else = error
    output?: string;
    error?: string;
}

/** One row of the diagnosis table (from the manual data capture API). */
export interface DiagnosisRow {
    copy: number | string;
    page: number | string;
    mse: number | null;
    sensitivity: number | null;
    timestamp_manual: number | null;
}

/** A copy/page pair, as sent to the AMC endpoints. */
export interface PagePosition {
    copy: string;
    page: string;
}
