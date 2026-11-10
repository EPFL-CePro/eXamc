import Konva from 'konva';

import type { PageShape } from './types.ts';

/** Shapes without their own style: blue outline, transparent fill (keeps the inside clickable). */
const DEFAULTS = { stroke: '#0d6efd', strokeWidth: 2, fill: 'transparent' };

/**
 * Creates the Konva node of a shape. Its outline keeps the same width at any zoom.
 *
 * @param {PageShape} shape - The shape.
 * @return {Konva.Line} The node.
 */
export function createShapeNode(shape: PageShape): Konva.Line {
    return new Konva.Line({
        points: shape.points,
        closed: true,
        stroke: shape.stroke ?? DEFAULTS.stroke,
        strokeWidth: shape.strokeWidth ?? DEFAULTS.strokeWidth,
        dash: shape.dash ?? [],
        fill: shape.fill ?? DEFAULTS.fill,
        strokeScaleEnabled: false,
        perfectDrawEnabled: false, // no offscreen pass for fill + stroke: cheaper with many shapes
    });
}
