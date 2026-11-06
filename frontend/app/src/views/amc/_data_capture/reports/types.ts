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
