import { canvas } from './elements.ts';
import { state } from './state.ts';
import type { MarkPosition, Point, Zone } from './types.ts';

const PLACEHOLDER_TEXT = 'Please select a page in the right panel';

/**
 * Groups mark corners into zones, in canvas coordinates.
 *
 * @param {MarkPosition[]} marks - The list of mark positions, 4 corners per zone.
 * @param {number} scale - Scan pixels -> canvas CSS pixels.
 * @param {Point} offset - Where the scan's top-left corner sits on the canvas.
 * @return {Zone[]} The zones.
 */
function buildZones(marks: MarkPosition[], scale: number, offset: Point): Zone[] {
    const result: Zone[] = [];
    let corners: Point[] = [];

    for (const mark of marks) {
        const point = { x: offset.x + mark.x * scale, y: offset.y + mark.y * scale };
        if (mark.corner === 1) corners = [point];
        else corners.push(point);

        if (mark.corner === 4 && corners.length === 4) {
            const [c1, c2, c3, c4] = corners as [Point, Point, Point, Point];
            result.push({
                zoneid: mark.zoneid,
                corner: mark.corner,
                why: mark.why ?? '',
                checked: Boolean(mark.checked),
                points: [c1, c2, c3, c4],
                left: c1.x,
                top: c1.y,
                right: c3.x,
                bottom: c4.y,
            });
        }
    }

    return result;
}

/**
 * Strokes the outline of a polygon.
 *
 * @param {CanvasRenderingContext2D} ctx - The rendering context.
 * @param {Point[]} points - The polygon's vertices.
 * @param {string} color - The stroke color.
 * @param {number} width - The stroke width.
 */
function strokePolygon(ctx: CanvasRenderingContext2D, points: Point[], color: string, width: number): void {
    const [first, ...rest] = points;
    if (!first) return;

    ctx.beginPath();
    ctx.moveTo(first.x, first.y);
    for (const point of rest) ctx.lineTo(point.x, point.y);
    ctx.closePath();
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();
}

/**
 * Draws one zone: an outer outline for invalid/empty answers, then the box itself.
 *
 * @param {CanvasRenderingContext2D} ctx - The rendering context.
 * @param {Zone} zone - The zone to draw.
 */
function drawZone(ctx: CanvasRenderingContext2D, zone: Zone): void {
    if (zone.why) {
        // Outer outline: yellow for invalid (E), cyan for empty (V)
        const [c1, c2, c3, c4] = zone.points;
        strokePolygon(ctx, [
            { x: c1.x - 2, y: c1.y - 2 },
            { x: c2.x + 2, y: c2.y - 2 },
            { x: c3.x + 2, y: c3.y + 2 },
            { x: c4.x - 2, y: c4.y + 2 },
        ], zone.why === 'E' ? '#FFFF33' : '#00FFFF', 5);
    }

    strokePolygon(ctx, zone.points, zone.checked ? '#ff0000' : '#33a3ff', zone.checked ? 3 : 1);
}

/**
 * Draws a centered message in the page's font.
 *
 * @param {CanvasRenderingContext2D} ctx - The rendering context.
 * @param {number} width - Canvas width in CSS pixels.
 * @param {number} height - Canvas height in CSS pixels.
 * @param {string} text - The message.
 */
function drawPlaceholder(ctx: CanvasRenderingContext2D, width: number, height: number, text: string): void {
    const style = getComputedStyle(canvas);
    ctx.font = `${parseFloat(style.fontSize) * 1.25}px ${style.fontFamily}`;
    ctx.fillStyle = '#6c757d'; // Bootstrap's secondary text color
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, width / 2, height / 2);
}

/**
 * Renders the current scan and its mark zones, or a placeholder when no page is selected.
 * The canvas size comes from CSS; the scan is fitted inside it, centered, keeping its own aspect ratio.
 */
export function draw(): void {
    // Size as laid out by CSS, in CSS pixels.
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (width === 0 || height === 0) return; // not laid out yet (hidden, or CSS not applied)

    // Backing store at device resolution so the scan stays sharp on high-DPI screens.
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    if (!state.view) {
        state.zones = [];
        drawPlaceholder(ctx, width, height, PLACEHOLDER_TEXT);
        return;
    }
    const { image, marks } = state.view;

    // Fit the scan inside the box ("contain") and center it.
    const scale = Math.min(width / image.naturalWidth, height / image.naturalHeight);
    const scanWidth = image.naturalWidth * scale;
    const scanHeight = image.naturalHeight * scale;
    const offset = { x: (width - scanWidth) / 2, y: (height - scanHeight) / 2 };

    ctx.drawImage(image, offset.x, offset.y, scanWidth, scanHeight);

    state.zones = buildZones(marks, scale, offset);
    for (const zone of state.zones) drawZone(ctx, zone);
}

/**
 * Returns the zone under a point in canvas CSS pixels, if any.
 *
 * @param {number} x - Horizontal position.
 * @param {number} y - Vertical position.
 * @return {Zone | undefined} The zone at that point.
 */
export function zoneAt(x: number, y: number): Zone | undefined {
    return state.zones.find((z) => x > z.left && x < z.right && y > z.top && y < z.bottom);
}