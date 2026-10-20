import html2canvas from "html2canvas-pro";
import { jsPDF, type jsPDFOptions } from "jspdf";
import { autoTable, type CellDef } from "jspdf-autotable";

const backgroundColor = "#fff";
const marginMM = 10;
const titleFontSize = 14;
const subtitleFontSize = 12;
/** Space between the title and the content. */
const titleSpacingMM = 8;
/** Space between the title and the subtitle, and between the subtitle and the content. */
const subtitleSpacingMM = 10;
/** Space between two blocks of content. */
const blockSpacingMM = 4;

/** Size of a CSS pixel, in mm (96 CSS pixels per inch). */
const mmPerPx = 25.4 / 96;
/** Size of a typographic point, in mm. */
const mmPerPt = 25.4 / 72;
const lineHeightRatio = 1.25;

/** Height of the table rows holding a chart. */
const chartRowHeightMM = 26;
/** Radius of the colored dots (e.g. a question's remark) in tables. */
const dotRadiusMM = 1.3;

/** Font size (pt) of text blocks, by tag; other text blocks use the paragraph's size. */
const textFontSizes: Record<string, number> = { H1: 20, H2: 16, H3: 14, H4: 13, H5: 12, H6: 11 };
const paragraphFontSize = 10;

/** Inline elements a text block may contain and still be written as text. */
const inlineTextTags = new Set(["A", "ABBR", "B", "BR", "CODE", "EM", "SMALL", "SPAN", "STRONG", "SUB", "SUP", "U"]);

/** Elements left out of exports: controls aren't content. */
const skippedTags = new Set(["BUTTON", "INPUT", "SELECT", "TEXTAREA", "SCRIPT", "STYLE", "TEMPLATE", "NOSCRIPT"]);

export interface RenderElToPdfOptions {
    /** The element to export. */
    el: HTMLElement | null;
    /** Name of the downloaded file. Defaults to "document.pdf". */
    fileName?: string;
    /** Text centered at the top of the first page. */
    title?: string;
    /** Text centered under the title. */
    subtitle?: string;
    /** Page size, e.g. "a4" or "letter". Defaults to "a4". */
    pageFormat?: jsPDFOptions["format"];
    /** "p" (portrait) or "l" (landscape). Defaults to portrait. */
    orientation?: jsPDFOptions["orientation"];
}

// ---------------------------------------------------------------------------
// Element helpers
// ---------------------------------------------------------------------------

/**
 * Whether an element is part of the export: shown on the page, not a control, and not marked
 * with data-pdf-skip.
 */
function isExported(element: Element): element is HTMLElement {
    return element instanceof HTMLElement
        && !skippedTags.has(element.tagName)
        && !element.hasAttribute("data-pdf-skip")
        && element.getClientRects().length > 0
        && getComputedStyle(element).visibility !== "hidden";
}

/** Whether an element only holds text (and inline formatting), so it can be written as text. */
function isTextOnly(element: HTMLElement): boolean {
    return (element.textContent ?? "").trim() !== ""
        && Array.from(element.querySelectorAll("*")).every((child) => inlineTextTags.has(child.tagName));
}

/**
 * The [r, g, b] of a computed CSS color ("rgb(0, 128, 0)").
 *
 * @return Its components, or null if it can't be read.
 */
function rgbComponents(color: string): [number, number, number] | null {
    const [r, g, b] = color.match(/\d+(\.\d+)?/g)?.map(Number) ?? [];
    return r === undefined || g === undefined || b === undefined ? null : [r, g, b];
}

/**
 * A table's rows as autoTable cells, keeping the page's cell elements (charts and dots are read
 * from them). A DataTable with a scrolling body keeps its visible header in a separate table: the
 * header is read from there.
 */
function tableRows(table: HTMLTableElement): { head: CellDef[][]; body: CellDef[][] } {
    const toCells = (row: HTMLTableRowElement): CellDef[] =>
        Array.from(row.cells, (cell) => ({
            content: cell.innerText.trim(),
            colSpan: cell.colSpan,
            rowSpan: cell.rowSpan,
            _element: cell,
        }));

    const headerTable = table.closest(".dt-container")?.querySelector<HTMLTableElement>(".dt-scroll-head table") ?? table;
    return {
        head: Array.from(headerTable.tHead?.rows ?? [], toCells),
        body: Array.from(table.tBodies).flatMap((section) => Array.from(section.rows, toCells)),
    };
}

// ---------------------------------------------------------------------------
// Writing
// ---------------------------------------------------------------------------

/** Writes blocks of content from the top of the document down, adding pages as needed. */
class PdfWriter {
    /** Where the next block goes, from the current page's top, in mm. */
    private y: number;

    constructor(readonly pdf: jsPDF, startY: number) {
        this.y = startY;
    }

    private get pageHeight(): number {
        return this.pdf.internal.pageSize.getHeight();
    }

    private get usableWidth(): number {
        return this.pdf.internal.pageSize.getWidth() - 2 * marginMM;
    }

    /** Free height left on the current page. */
    private get spaceLeft(): number {
        return this.pageHeight - marginMM - this.y;
    }

    /** Starts a new page if a block of this height doesn't fit on the current one. */
    private ensureSpace(heightMM: number): void {
        if (heightMM > this.spaceLeft && this.y > marginMM) {
            this.pdf.addPage();
            this.y = marginMM;
        }
    }

    /** Leaves space before the next block, unless it starts a page. */
    private gap(): void {
        if (this.y > marginMM) this.y += blockSpacingMM;
    }

    /** A text block (heading or paragraph), wrapped to the page's width. */
    text(element: HTMLElement): void {
        const fontSize = textFontSizes[element.tagName] ?? paragraphFontSize;
        const lineHeight = fontSize * mmPerPt * lineHeightRatio;

        this.gap();
        this.pdf.setFont("helvetica", element.tagName in textFontSizes ? "bold" : "normal");
        this.pdf.setFontSize(fontSize);

        const lines = this.pdf.splitTextToSize(element.innerText.trim(), this.usableWidth) as string[];
        for (const line of lines) {
            this.ensureSpace(lineHeight);
            this.pdf.text(line, marginMM, this.y + fontSize * mmPerPt); // y is the text's baseline
            this.y += lineHeight;
        }
        this.pdf.setFont("helvetica", "normal");
    }

    /**
     * An image, at its size on the page (shrunk to the page's width if wider). Images taller than
     * a page are cut across as many pages as needed.
     *
     * @param canvas - The image.
     * @param cssWidth - Its width on the page, in CSS pixels.
     */
    image(canvas: HTMLCanvasElement, cssWidth: number): void {
        if (canvas.width === 0 || canvas.height === 0) return;

        const widthMM = Math.min(cssWidth * mmPerPx, this.usableWidth);
        const pxPerMM = canvas.width / widthMM;
        const heightMM = canvas.height / pxPerMM;

        this.gap();
        this.ensureSpace(Math.min(heightMM, this.pageHeight - 2 * marginMM));

        let sliceTopPx = 0;
        while (sliceTopPx < canvas.height) {
            if (sliceTopPx > 0) {
                this.pdf.addPage();
                this.y = marginMM;
            }
            const sliceHeightPx = Math.min(Math.floor(this.spaceLeft * pxPerMM), canvas.height - sliceTopPx);

            const slice = document.createElement("canvas");
            slice.width = canvas.width;
            slice.height = sliceHeightPx;
            const ctx = slice.getContext("2d");
            if (!ctx) throw new Error("Couldn't initialize 2D canvas for renderElToPdf!");
            ctx.drawImage(canvas, 0, sliceTopPx, canvas.width, sliceHeightPx, 0, 0, canvas.width, sliceHeightPx);

            this.pdf.addImage(slice.toDataURL("image/png"), "PNG", marginMM, this.y, widthMM, sliceHeightPx / pxPerMM);
            this.y += sliceHeightPx / pxPerMM;
            sliceTopPx += sliceHeightPx;
        }
    }

    /** Any other block, captured as it looks on the page. */
    async raster(element: HTMLElement): Promise<void> {
        const canvas = await html2canvas(element, {
            backgroundColor,
            scale: Math.max(window.devicePixelRatio || 1, 2),
        });
        this.image(canvas, element.getBoundingClientRect().width);
    }

    /**
     * A table, as a real PDF table: selectable text, rows never cut across pages, the header
     * repeated on each page. Charts in cells are added as images, colored dots as circles.
     */
    table(table: HTMLTableElement): void {
        const { head, body } = tableRows(table);
        // autoTable replaces a cell's raw input by its _element when there is one.
        const elementOf = (raw: unknown): HTMLTableCellElement | undefined =>
            raw instanceof HTMLTableCellElement ? raw : undefined;

        this.gap();
        autoTable(this.pdf, {
            head,
            body,
            startY: this.y,
            margin: { top: marginMM, right: marginMM, bottom: marginMM, left: marginMM },
            theme: "striped",
            rowPageBreak: "avoid",
            styles: { fontSize: 8, valign: "middle", overflow: "linebreak" },
            headStyles: { fillColor: [33, 37, 41] },

            // Cells holding a chart: no text, room for the chart, and a width: the cell's
            // data-pdf-width (mm) if set, else its share of the table's width on the page.
            didParseCell: ({ cell }) => {
                const element = elementOf(cell.raw);
                if (!element?.querySelector("canvas")) return;

                cell.text = [];
                cell.styles.minCellHeight = chartRowHeightMM;

                const explicitWidth = Number(element.dataset["pdfWidth"]);
                const share = element.getBoundingClientRect().width / table.getBoundingClientRect().width;
                cell.styles.cellWidth = explicitWidth > 0 ? explicitWidth : share * this.usableWidth;
            },

            // Charts and dots are drawn over their (empty) cells.
            didDrawCell: ({ cell }) => {
                const element = elementOf(cell.raw);
                if (!element) return;

                const canvas = element.querySelector("canvas");
                if (canvas && canvas.width > 0 && canvas.height > 0) {
                    const ratio = canvas.width / canvas.height;
                    let width = cell.width - 2;
                    let height = width / ratio;
                    if (height > cell.height - 2) {
                        height = cell.height - 2;
                        width = height * ratio;
                    }
                    this.pdf.addImage(canvas.toDataURL("image/png"), "PNG",
                        cell.x + (cell.width - width) / 2, cell.y + (cell.height - height) / 2, width, height);
                }

                const dot = element.querySelector("i.fa-circle");
                const color = dot ? rgbComponents(getComputedStyle(dot).color) : null;
                if (color) {
                    this.pdf.setFillColor(...color);
                    this.pdf.circle(cell.x + cell.width / 2, cell.y + cell.height / 2, dotRadiusMM, "F");
                }
            },
        });

        // autoTable may have added pages: continue under the table, on its last page.
        const finalY = (this.pdf as jsPDF & { lastAutoTable?: { finalY?: number } }).lastAutoTable?.finalY;
        this.y = finalY ?? this.y;
    }

    /**
     * An element of the page: tables become PDF tables, charts images, text blocks text.
     * Containers holding a table or a chart are walked into; any other block is captured as an image.
     */
    async block(element: Element): Promise<void> {
        if (!isExported(element)) return;

        if (element instanceof HTMLTableElement) {
            // DataTables' copies of the header and footer, kept for scrolling, are read with the table itself.
            if (!element.closest(".dt-scroll-head, .dt-scroll-foot")) this.table(element);
        } else if (element instanceof HTMLCanvasElement) {
            this.image(element, element.getBoundingClientRect().width);
        } else if (isTextOnly(element)) {
            this.text(element);
        } else if (element.querySelector("table, canvas")) {
            for (const child of Array.from(element.children)) await this.block(child);
        } else {
            await this.raster(element);
        }
    }
}

/**
 * Draws the document's title and subtitle, at the top of the first page.
 *
 * @return Where the content starts, from the page's top, in mm.
 */
function drawTitles(pdf: jsPDF, title?: string, subtitle?: string): number {
    const pageWidth = pdf.internal.pageSize.getWidth();
    let bodyTopMM = marginMM;
    if (title) {
        pdf.setFontSize(titleFontSize);
        pdf.text(title, pageWidth / 2, marginMM, { align: "center" });
        bodyTopMM += titleSpacingMM;

        if (subtitle) {
            pdf.setFontSize(subtitleFontSize);
            pdf.text(subtitle, pageWidth / 2, marginMM + subtitleSpacingMM, { align: "center" });
            bodyTopMM += subtitleSpacingMM;
        }
    }
    return bodyTopMM;
}

/**
 * Downloads an element of the page as a PDF, keeping what can be kept as real PDF content:
 * tables become PDF tables (selectable text, rows never cut, header repeated on each page),
 * charts images, headings and paragraphs text. Anything else is captured as it looks on the page.
 * Controls (buttons, inputs) and elements marked data-pdf-skip are left out.
 *
 * @param options - What to export and how.
 * @throws If no element is given.
 */
export async function renderElToPdf(options: RenderElToPdfOptions): Promise<void> {
    const { el, fileName = "document.pdf", title, subtitle, pageFormat = "a4", orientation = "p" } = options;
    if (!el) throw new Error("A valid HTMLElement wasn't passed to renderElToPdf");

    const pdf = new jsPDF({ orientation, unit: "mm", format: pageFormat });
    const writer = new PdfWriter(pdf, drawTitles(pdf, title, subtitle));
    await writer.block(el);

    pdf.save(fileName);
}