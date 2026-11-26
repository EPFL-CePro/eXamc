import type { AnnotationState } from '@markerjs/markerjs3';

export type Tool = 'select' | 'pan' | 'text' | 'rectangle' | 'freehand';

/** What the review page is showing; shared by the modules. */
export const state = {
    /** Position (0-based) in the review group of the page shown, or of the last group page shown. */
    entryIndex: 0,
    /** The page shown (it can be a page of the copy outside the review group). */
    copyNo: null as string | null,
    pageNo: null as string | null,
    /** Whether the page shown is part of the review group. */
    inGroup: true,
    /** The URL of the page's scan (saved with its markers). */
    scanSrc: '',

    /** The grading scheme whose panel is shown. */
    gradingSchemeId: null as string | null,

    /** The page's markers: as last loaded or saved, and as last confirmed by the server. */
    markerState: null as AnnotationState | null,
    lastPersistedMarkerState: null as AnnotationState | null,

    tool: 'select' as Tool,
    /** The color picked for drawing: kept across tools and pages, and given to each new marker. */
    drawingColor: '#CCCCCC',
};
