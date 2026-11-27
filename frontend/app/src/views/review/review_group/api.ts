import type { AnnotationState } from '@markerjs/markerjs3';
import { parseJson, postText } from '@examc/helpers/http.ts';
import { config, type GroupEntry } from './config';
import type { CorrectorBoxCorner } from './viewer/corrector-boxes';

/** The review page's server calls. They throw an HttpError when the server answers with an error. */

/** A page's data, as returned by get_markers_and_comments. */
export interface PageData {
    /** "<prefix>/<folder>/<prefix>_<copy>_<page>/<file>": the scan's location and its copy and page. */
    copyPageUrl: string;
    markers: AnnotationState;
    comments: unknown[];
    correctorBoxes: CorrectorBoxCorner[];
    copyPages: GroupEntry[];
}

type Fields = Record<string, string | number | boolean | null | undefined>;

/** Form fields for the http helpers; a missing value is sent empty. */
function fields(data: Fields): Record<string, string | number | boolean> {
    return Object.fromEntries(Object.entries(data).map(([key, value]) => [key, value ?? '']));
}

/** Whether another reviewer has this copy open (it can't be opened then). */
export async function isCopyLocked(copyNo: string): Promise<boolean> {
    const answer = await postText(config.urls.reviewStudentPageLocked, fields({pages_group_id: config.pagesGroupId, copy_no: copyNo}));
    return answer !== '';
}

/** A page's scan, markers, comments and corrector boxes; null if there's none. */
export async function fetchPage(copyNo: string, pageNo: string): Promise<PageData | null> {
    const text = await postText(config.urls.getMarkersAndComments, fields({copy_no: copyNo, page_no: pageNo, group_id: config.pagesGroupId}));
    return text === 'None' ? null : parseJson<PageData>(text);
}

/** Tells the server which page of a copy (inside or outside the review group) is opened next. */
export async function requestCopyPage(copyNo: string, pageNo: string): Promise<void> {
    await postText(config.urls.getCopyPage, fields({copy_no: copyNo, page_no: pageNo}));
}

export interface SaveMarkersParams {
    copyNo: string;
    pageNo: string;
    rowId: string;
    markers: AnnotationState;
    scanSrc: string;
    allowHighlightOnly: boolean;
    allowEmpty: boolean;
}

/** Saves a page's markers; resolves to whether the page now counts as graded. */
export async function saveMarkers(params: SaveMarkersParams): Promise<boolean> {
    const marked = await postText(config.urls.saveMarkers, fields({
        reviewGroup_pk: config.pagesGroupId,
        curr_row: params.rowId,
        copy_no: params.copyNo,
        page_no: params.pageNo,
        markers: JSON.stringify(params.markers),
        filename: params.scanSrc,
        allow_highlight_only_replace: params.allowHighlightOnly,
        allow_empty_replace: params.allowEmpty,
    }));
    return marked === 'True';
}

/** Saves a comment (`comment`: its JSON), or deletes one (`comment_id` and `delete`). */
export async function saveComment(copyNo: string, data: {comment?: string; comment_id?: string | number; delete?: boolean}): Promise<void> {
    await postText(config.urls.saveComment, fields({group_id: config.pagesGroupId, copy_no: copyNo, ...data}));
}

export async function saveStudentNote(pagesGroupId: string, copyNo: string, content: string): Promise<void> {
    await postText(config.urls.savePagesGroupStudentNote, fields({pages_group_id: pagesGroupId, copy_nr: copyNo, content}));
}

/** Ticks or unticks a mark (or sets an adjustment); resolves to the server's JSON answer, or ''. */
export function updateCheckBox(data: Fields): Promise<string> {
    return postText(config.urls.updatePagesGroupCheckBox, fields({pages_group_id: config.pagesGroupId, ...data}));
}