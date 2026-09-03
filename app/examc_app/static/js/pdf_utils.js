// static/js/pdf_utils.js
const backgroundColor = '#fff';
const marginMM = 10;
const titleFontSize = 14;
const subtitleFontSize = 12;
const titleSpacingMM = 8;

async function downloadElementAsPDF({
                                        elementId,
                                        fileName = 'document.pdf',
                                        title = null,                 // optional text header on first page
                                        subtitle = null,
                                        pageFormat = 'a4',            // 'a4', 'letter', etc.
                                        orientation = 'p',
                                    } = {}) {
    const el = document.getElementById(elementId);
    if (!el) throw new Error(`#${elementId} not found`);

    const canvas = await html2canvas(el, {
        backgroundColor,
        scale: Math.max(window.devicePixelRatio || 1, 2),
        onclone: (doc) => {
            const clonedEl = doc.getElementById(elementId);
            if (!clonedEl) return;

            const toLoosen = [clonedEl].concat(
                Array.from(
                    doc.querySelectorAll('#' + CSS.escape(elementId) + ' [style*="overflow"]')
                )
            );

            toLoosen.forEach(n => {
                n.style.overflow = 'visible';
                n.style.height = 'auto';
                n.style.maxHeight = 'none';
                if (getComputedStyle(n).position === 'fixed') {
                    n.style.position = 'static';
                }
            });
        }
    });

    const {jsPDF} = window.jspdf;
    const pdf = new jsPDF(orientation, 'mm', pageFormat);

    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();

    // Where the body actually starts
    var bodyTopMM = title ? (marginMM + titleSpacingMM) : marginMM;
    if(subtitle){
        bodyTopMM+=10;
    }

    const usableWidthMM = pageWidth - 2 * marginMM;
    const usableHeightMM = pageHeight - bodyTopMM - marginMM; // top body + bottom margin

    const canvasWidthPx = canvas.width;
    const canvasHeightPx = canvas.height;

    const pxPerMM = canvasWidthPx / usableWidthMM;
    const pageHeightPx = usableHeightMM * pxPerMM;

    // Draw title (if any)
    if (title) {
        pdf.setFontSize(titleFontSize);
        // put title slightly above bodyTopMM
        const titleY = marginMM;  // or bodyTopMM - (titleSpacingMM / 2)
        pdf.text(title, pageWidth / 2, titleY, {align: 'center'});
        if (subtitle){
            pdf.setFontSize(subtitleFontSize);
            pdf.text(subtitle, pageWidth / 2, titleY+10, {align: 'center'});
        }
    }

    // --- Single-page case ---
    if (canvasHeightPx <= pageHeightPx) {
        const imgData = canvas.toDataURL('image/png');
        pdf.addImage(
            imgData,
            'PNG',
            marginMM,               // X
            bodyTopMM,              // Y: starts below title + spacing
            usableWidthMM,
            canvasHeightPx / pxPerMM
        );
        pdf.save(fileName);
        return;
    }

    // --- Multi-page: slice into parts ---
    let remainingHeightPx = canvasHeightPx;
    let pageIndex = 0;

    while (remainingHeightPx > 0) {
        const startY = pageIndex * pageHeightPx;

        const pageCanvas = document.createElement('canvas');
        pageCanvas.width = canvasWidthPx;
        pageCanvas.height = Math.min(pageHeightPx, remainingHeightPx);

        const ctx = pageCanvas.getContext('2d');
        ctx.drawImage(
            canvas,
            0,
            startY,
            canvasWidthPx,
            pageCanvas.height,
            0,
            0,
            canvasWidthPx,
            pageCanvas.height
        );

        const pageImgData = pageCanvas.toDataURL('image/png');
        if (pageIndex > 0) pdf.addPage();

        const y = (pageIndex === 0) ? bodyTopMM : marginMM; // first page respects title spacing
        pdf.addImage(
            pageImgData,
            'PNG',
            marginMM,
            y,
            usableWidthMM,
            pageCanvas.height / pxPerMM
        );

        remainingHeightPx -= pageHeightPx;
        pageIndex++;
    }

    pdf.save(fileName);
}
