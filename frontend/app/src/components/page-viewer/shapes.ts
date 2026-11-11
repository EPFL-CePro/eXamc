import Konva from 'konva';

import type { PageShape } from './types.ts';
import { AMC_UNCHECKED_BOX } from '@examc/helpers/amc.ts';

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
        stroke: shape.stroke ?? AMC_UNCHECKED_BOX.stroke,
        strokeWidth: shape.strokeWidth ?? AMC_UNCHECKED_BOX.strokeWidth,
        dash: shape.dash ?? [],
        fill: shape.fill ?? AMC_UNCHECKED_BOX.fill,
        strokeScaleEnabled: true,
        perfectDrawEnabled: false, // no offscreen pass for fill + stroke: cheaper with many shapes
    });
}