/** One page of the review group, as listed by the server (also the rows of the pages table). */
export interface GroupEntry {
    copyNo: string;
    pageNo: string;
    marked?: boolean;
    comment?: boolean;
}

/** Configuration injected by review_group.html, before this script runs. */
export interface ReviewGroupConfig {
    examId: number;
    pagesGroupId: number;
    useGradingScheme: boolean;
    userId: number;
    /** 1-based position of the page to open first (the ?page_id= of the URL), 0 for the first one. */
    currPage: number;
    csrfToken: string;
    urls: {
        reviewStudentPageLocked: string;
        getMarkersAndComments: string;
        getCopyPage: string;
        saveMarkers: string;
        saveComment: string;
        savePagesGroupStudentNote: string;
        updatePagesGroupCheckBox: string;
        reviewGradingSchemePanelBase: string;
    };
    copiesPagesList: GroupEntry[];
    totalCopiesPages: number;
}

declare global {
    interface Window {
        REVIEW_GROUP_CONFIG?: ReviewGroupConfig;
    }
}

if (!window.REVIEW_GROUP_CONFIG) {
    throw new Error('REVIEW_GROUP_CONFIG is missing: review_group.html must define it before loading this script.');
}

export const config: ReviewGroupConfig = window.REVIEW_GROUP_CONFIG;

/** The pages of the review group, in the order of the table. */
export const entries: GroupEntry[] = config.copiesPagesList ?? [];

/** Position (0-based) of a copy's page in the review group, or -1 if the page isn't part of it. */
export function entryIndexOf(copyNo: string, pageNo: string): number {
    return entries.findIndex((entry) => String(entry.copyNo) === copyNo && String(entry.pageNo) === pageNo);
}
