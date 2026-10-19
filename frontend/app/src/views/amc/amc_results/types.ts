export type CellValue = string | number | null;

/** One row of the send dialog's students table. Keys are column names, sent by the server. */
export type StudentRow = Record<string, CellValue>;

/** Endpoints used by results.ts. */
export interface ResultsUrls {
    generate: string;
}

/** Endpoints used by annotate.ts. */
export interface AnnotateUrls {
    annotate: string;
}

/** Endpoints used by send.ts. */
export interface SendUrls {
    sendData: string;
    send: string;
}

/** Response of the send data view: students table and default email. */
export interface SendDataResponse {
    data?: StudentRow[];
    email_subject?: string;
    email_text?: string;
}

/** Response of the annotate view: where to poll the job status. */
export interface AnnotateStartResponse {
    status_url: string;
}

/** Status of an annotation job. */
export interface AnnotateStatusResponse {
    status: string; // "queued" | "running" | "done" | anything else = failed
    progress?: string;
    error?: string;
}

/** Response of the send view: [sent count, not sent count, details]. */
export type SendResultResponse = [sent: number, notSent: number, details: string[]];

/** A student selected in the send dialog, as sent to the server. */
export interface SelectedStudent {
    id: CellValue;
    copy: CellValue;
    email: CellValue;
}

/** The email being written in the send dialog, kept when it's closed. */
export interface EmailDraft {
    subject: string;
    /** Markdown, as the editor takes it back. */
    body: string;
}

/** What the send dialog asks to send. */
export interface SendRequest {
    emailColumn: string;
    subject: string;
    /** HTML. */
    body: string;
    students: SelectedStudent[];
}