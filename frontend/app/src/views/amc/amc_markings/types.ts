/** Endpoints and token used by marking.ts. */
export interface MarkingConfig {
    mark: string;
    /** Sent in the request body, since the marking output is streamed with a plain fetch. */
    csrfToken: string;
}

/** Endpoints used by students.ts. */
export interface StudentsUrls {
    updateFile: string;
    editFile: string;
    saveFile: string;
    /** Page reloaded after the students list changed. */
    amcView: string;
}

/** Endpoints used by association.ts. */
export interface AssociationUrls {
    automatic: string;
    manualData: string;
    setManual: string;
}

/** One answer sheet, as returned by amc_manual_association_data (data_assoc). */
export interface AssociationRow {
    /** Sheet number (AMC's `student` column), shown as "Copy Nr.". */
    student: number | string;
    /** Copy number; 0 unless sheets were photocopied. */
    copy?: number | string;
    /** Student code found by automatic association. */
    auto: number | string | null;
    /** Student code set by hand; 'NONE' means explicitly no student, overriding `auto`. */
    manual: number | string | null;
    image_path: string;
}

/** Response of amc_set_manual_association. */
export interface SetManualAssociationResponse {
    ok: boolean;
    error?: string;
}

/** One row of the students list (data_students). The first row is the CSV header. */
export type StudentRow = [id: number | string, first: string, second: string, ...rest: unknown[]];

/** Response of amc_manual_association_data. Both fields are JSON strings. */
export interface ManualAssociationPayload {
    data_assoc: AssociationRow[];
    data_students: StudentRow[];
}

/** Response of call_amc_automatic_association. */
export interface AutoAssociationResponse {
    ok: boolean;
    redirect?: string;
    error?: string;
}

/** Response of edit_amc_file: [filepath, file content]. */
export type EditFileResponse = [filepath: string, content: string];

/** One row of the students list CSV, one string per column. */
export type StudentsListRow = string[];

/** How the students list CSV was written, so it is saved back the same way. */
export interface CsvFormat {
    delimiter: string;
    lineEnding: '\r\n' | '\n';
    trailingNewline: boolean;
    /** Comment lines (starting with #) before the header, kept as they were. */
    preamble: string[];
}

/** The students list open in the edit dialog. */
export interface StudentsListFile {
    filepath: string;
    header: string[];
    format: CsvFormat;
}