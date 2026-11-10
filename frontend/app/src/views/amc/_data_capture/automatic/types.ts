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
