import type { CsvFormat, StudentsListRow } from '../types.ts';

/** Delimiters AMC accepts for the students list. */
const DELIMITERS = [',', ';', '\t'] as const;

/** Thrown when the students list is not a valid CSV. The message is meant for the user. */
export class CsvError extends Error {
    /** Line of the file where the problem is, if known. */
    readonly line: number | undefined;

    constructor(message: string, line?: number) {
        super(line === undefined ? message : `Line ${line}: ${message}`);
        this.name = 'CsvError';
        this.line = line;

        // Set the prototype explicitly to maintain the correct prototype chain
        Object.setPrototypeOf(this, CsvError.prototype);
    }
}

/** A parsed record and the line it starts on. */
interface CsvRecord {
    fields: string[];
    line: number;
}

/**
 * Names a delimiter for error messages.
 *
 * @param {string} delimiter - The delimiter.
 * @return {string} Its display name.
 */
const delimiterName = (delimiter: string): string => (delimiter === '\t' ? 'tab' : `"${delimiter}"`);

/**
 * Counts a character in a line, ignoring quoted parts.
 *
 * @param {string} line - The line.
 * @param {string} char - The character.
 * @return {number} The count.
 */
function countOutsideQuotes(line: string, char: string): number {
    let inQuotes = false;
    let count = 0;
    for (const c of line) {
        if (c === '"') inQuotes = !inQuotes;
        else if (!inQuotes && c === char) count++;
    }
    return count;
}

/**
 * Picks the delimiter used by the header line.
 *
 * @param {string} headerLine - The CSV's header line.
 * @return {string} The most frequent delimiter, ',' if none is found (single column).
 */
function detectDelimiter(headerLine: string): string {
    let best: string = ',';
    let bestCount = 0;
    for (const delimiter of DELIMITERS) {
        const count = countOutsideQuotes(headerLine, delimiter);
        if (count > bestCount) {
            best = delimiter;
            bestCount = count;
        }
    }
    return best;
}

/**
 * Parses CSV records following RFC 4180: fields may be quoted, quotes inside quoted fields are doubled,
 * and quoted fields may contain delimiters and line breaks. Blank lines are skipped.
 *
 * @param {string} text - The CSV text, without the preamble.
 * @param {string} delimiter - The field delimiter.
 * @param {number} firstLine - Line number of the text's first line in the file.
 * @return {CsvRecord[]} The records.
 * @throws {CsvError} On a stray or unclosed quote.
 */
function parseRecords(text: string, delimiter: string, firstLine: number): CsvRecord[] {
    const records: CsvRecord[] = [];
    let fields: string[] = [];
    let field = '';
    let inQuotes = false;
    let afterQuote = false; // just closed a quoted field: only a delimiter or line break may follow
    let line = firstLine;
    let recordLine = line;
    let quoteLine = line;

    const endRecord = (): void => {
        fields.push(field);
        if (!(fields.length === 1 && fields[0] === '')) records.push({ fields, line: recordLine });
        fields = [];
        field = '';
        afterQuote = false;
    };

    for (let i = 0; i < text.length; i++) {
        const c = text.charAt(i);

        if (inQuotes) {
            if (c === '"') {
                if (text.charAt(i + 1) === '"') {
                    field += '"';
                    i++;
                } else {
                    inQuotes = false;
                    afterQuote = true;
                }
            } else {
                if (c === '\n') line++;
                field += c;
            }
            continue;
        }

        if (c === delimiter) {
            fields.push(field);
            field = '';
            afterQuote = false;
        } else if (c === '\n' || c === '\r') {
            if (c === '\r' && text.charAt(i + 1) === '\n') i++;
            endRecord();
            line++;
            recordLine = line;
        } else if (afterQuote) {
            throw new CsvError('unexpected text after a closing quote. Quote the whole field.', line);
        } else if (c === '"') {
            if (field !== '') {
                throw new CsvError('quote inside an unquoted field. Quote the whole field and double the quote ("").', line);
            }
            inQuotes = true;
            quoteLine = line;
        } else {
            field += c;
        }
    }

    if (inQuotes) throw new CsvError('a quoted field is never closed.', quoteLine);
    if (field !== '' || fields.length > 0 || afterQuote) endRecord();

    return records;
}

/**
 * Reads a students list CSV: a header line, then one line per student with the same number of fields.
 *
 * @param {string} text - The file content.
 * @return {{ header: string[]; rows: StudentsListRow[]; format: CsvFormat }} The header, rows and format.
 * @throws {CsvError} If the content is not a valid students list CSV.
 */
export function readCsv(text: string): { header: string[]; rows: StudentsListRow[]; format: CsvFormat } {
    const lineEnding = text.includes('\r\n') ? '\r\n' : '\n';
    const lines = text.split(/\r?\n/);

    // AMC ignores lines starting with '#': keep the leading ones aside, untouched.
    const preamble: string[] = [];
    while (lines[0]?.startsWith('#')) preamble.push(lines.shift() as string);

    const delimiter = detectDelimiter(lines.find((line) => line.trim() !== '') ?? '');
    const [header, ...records] = parseRecords(lines.join('\n'), delimiter, preamble.length + 1);

    if (!header) throw new CsvError('The students list is empty.');
    if (header.fields.some((name) => name.trim() === '')) {
        throw new CsvError('the header has an empty column name.', header.line);
    }

    const width = header.fields.length;
    for (const record of records) {
        if (record.fields.length !== width) {
            throw new CsvError(
                `expected ${width} fields like the header, found ${record.fields.length} `
                + `(fields are separated by ${delimiterName(delimiter)}).`,
                record.line,
            );
        }
    }

    return {
        header: header.fields,
        rows: records.map((record) => record.fields),
        format: { delimiter, lineEnding, trailingNewline: /\r?\n$/.test(text), preamble },
    };
}

/**
 * Quotes a field when it contains the delimiter, a quote or a line break.
 *
 * @param {string} field - The field.
 * @param {string} delimiter - The field delimiter.
 * @return {string} The field, quoted if needed.
 */
function quote(field: string, delimiter: string): string {
    return field.includes(delimiter) || /["\r\n]/.test(field) ? `"${field.replace(/"/g, '""')}"` : field;
}

/**
 * Writes a students list CSV in the format it was read with.
 *
 * @param {string[]} header - The header.
 * @param {StudentsListRow[]} rows - The rows.
 * @param {CsvFormat} format - The original format.
 * @return {string} The CSV text.
 */
export function writeCsv(header: string[], rows: StudentsListRow[], format: CsvFormat): string {
    const { delimiter, lineEnding, trailingNewline, preamble } = format;
    const lines = [
        ...preamble,
        ...[header, ...rows].map((row) => row.map((field) => quote(field, delimiter)).join(delimiter)),
    ];
    return lines.join(lineEnding) + (trailingNewline ? lineEnding : '');
}