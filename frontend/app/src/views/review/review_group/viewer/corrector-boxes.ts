import { config } from '../config';
import { highlightBox } from '../markers';
import { currentArea, getMarkerStage } from './area';

/** One corner of a corrector box, in the scan's pixels; corners 1 to 4 of a box follow each other. */
export interface CorrectorBoxCorner {
    x: number;
    y: number;
    corner: number;
}

const SVG_NS = 'http://www.w3.org/2000/svg';

let corners: CorrectorBoxCorner[] = [];

/** The current page's corrector boxes. */
export function setCorrectorBoxes(pageCorners: CorrectorBoxCorner[]): void {
    corners = pageCorners;
}

/** The overlay holding the boxes, inside marker.js's stage so it zooms and pans with the page. */
function getOverlay(): HTMLElement | null {
    const stage = getMarkerStage();
    if (!stage) return null;

    let overlay = stage.querySelector<HTMLElement>('#corr_box_div');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'corr_box_div';
        Object.assign(overlay.style, {
            position: 'absolute', left: '0', top: '0', width: '100%', height: '100%', margin: '0',
            zIndex: '1000', pointerEvents: 'none', gridColumnStart: '1', gridRowStart: '1',
        });
        stage.appendChild(overlay);
    }
    return overlay;
}

/**
 * Draws the boxes as SVG polygons over the page, scaled to the fitted page.
 * @param scanNaturalWidth The scan's width in pixels: the boxes' coordinates are in its pixels.
 */
export function drawCorrectorBoxes(scanNaturalWidth: number): void {
    const overlay = getOverlay();
    if (!overlay) return;
    overlay.replaceChildren();
    if (!corners.length) return;

    const area = currentArea();
    const scale = area.targetWidth / (scanNaturalWidth || 1);

    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.id = 'corrector_boxes_svg';
    svg.setAttribute('width', `${area.targetWidth}`);
    svg.setAttribute('height', `${area.targetHeight}`);
    svg.setAttribute('viewBox', `0 0 ${area.targetWidth} ${area.targetHeight}`);
    svg.setAttribute('style', 'width: 100%; height: 100%; pointer-events: none;');
    overlay.appendChild(svg);

    let polygon: SVGPolygonElement | null = null;
    let left = 0;
    let top = 0;
    let width = 0;

    for (const point of corners) {
        const x = point.x * scale;
        const y = point.y * scale;

        if (point.corner === 1) {
            left = x;
            top = y;
            polygon = document.createElementNS(SVG_NS, 'polygon');
        }
        if (!polygon) continue;

        const svgPoint = svg.createSVGPoint();
        svgPoint.x = x;
        svgPoint.y = y;
        polygon.points.appendItem(svgPoint);

        if (point.corner === 2) width = x - left;

        if (point.corner === 4) {
            const bounds = {left, top, width, height: y - top};
            polygon.setAttribute('fill', 'transparent');
            polygon.setAttribute('stroke', 'purple');
            polygon.setAttribute('stroke-width', '3');
            polygon.setAttribute('opacity', '0.7');
            polygon.dataset['bounds'] = `${bounds.left},${bounds.top},${bounds.width},${bounds.height}`;
            polygon.style.pointerEvents = 'all';

            // Without grading schemes, clicking a box marks it (with one, the scheme decides the box)
            if (!config.useGradingScheme) {
                polygon.addEventListener('click', (event) => {
                    event.stopPropagation();
                    highlightBox(bounds.left, bounds.top, bounds.width, bounds.height);
                });
            }

            svg.appendChild(polygon);
            polygon = null;
        }
    }
}

/**
 * Highlights the corrector box at `index` (-1: none), once it's drawn. Retries for a few frames,
 * since a scheme's answer can arrive before its page is drawn.
 */
export function highlightCorrectorBox(index: number, tries = 20): void {
    if (index === -1) {
        highlightBox(-1, -1, -1, -1, false);
        return;
    }
    if (!corners.length) return;

    const polygon = getOverlay()?.querySelectorAll<SVGPolygonElement>('#corrector_boxes_svg polygon')[index];
    if (!polygon?.dataset['bounds']) {
        if (tries > 0) requestAnimationFrame(() => highlightCorrectorBox(index, tries - 1));
        return;
    }

    const [left, top, width, height] = polygon.dataset['bounds'].split(',').map(Number);
    if (left === undefined || top === undefined || width === undefined || height === undefined) return;
    highlightBox(left, top, width, height, false);
}