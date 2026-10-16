/** URLs given by the template (exam_preparation.html); the `__X__` ones are templates to fill with `.replace`. */
export interface ExamPrepUrls {
    previewStart: string;
    previewStatus: string;
    reorderSections: string;
    reorderQuestionsTemplate: string;
    reorderAnswersTemplate: string;
    scoringFormulasModal: string;
    editLatexFile: string;
    saveLatexFile: string;
    editLatexPackages: string;
    saveLatexPackages: string;
    generateFinalStart: string;
    cancelFinal: string;
    celeryTaskStatusTemplate: string;
}

export interface ExamPrepConfig {
    csrfToken: string;
    examPk: string;
    isFinalized: boolean;
    /** Finalized, or a final generation is running: nothing can be modified. */
    isLocked: boolean;
    /** Celery task of a final generation still running when the page was loaded. */
    activeFinalTaskId: string;
    activeFinalStartedAt: string;
    urls: ExamPrepUrls;
}

/** Functions called by the onclick attributes of the template. */
interface ExamPrepGlobals {
    previewExam: () => void;
    openEditLaTeXFileDialog: (type: string) => void;
    saveEditedLaTeXFile: () => void;
    openEditLaTeXPackagesDialog: (type: string) => void;
    saveEditedLaTeXPackages: () => void;
    generateFinalExamFiles: (confirmWarnings?: boolean) => void;
    openUnlockEditingModal: () => void;
}

declare global {
    interface Window extends Partial<ExamPrepGlobals> {
        EXAM_PREP_CONFIG?: ExamPrepConfig;
    }
}

const EMPTY_CONFIG: ExamPrepConfig = {
    csrfToken: "",
    examPk: "",
    isFinalized: false,
    isLocked: false,
    activeFinalTaskId: "",
    activeFinalStartedAt: "",
    urls: {} as ExamPrepUrls,
};

export const CFG: ExamPrepConfig = window.EXAM_PREP_CONFIG ?? EMPTY_CONFIG;
export const URLS: ExamPrepUrls = CFG.urls;
export const CSRF: string = CFG.csrfToken;
export const EXAM_PK: string = CFG.examPk;

export const Selectors = {
    loadingModal: "#loadingModal",
    sectionList: "#prep-sections-list",
    scoringModal: "#modalScoringFormulas",
    scoringModalBody: "#modalScoringFormulasBody",
    openScoringModalBtn: ".open-scoring-formulas-modal",
    scoringForm: "#scoringFormulasForm",
    dragHandle: ".drag-handle",
} as const;

/** Finalized, or a final generation is running: read-only. */
export function isExamFinalized(): boolean {
    return Boolean(window.EXAM_PREP_CONFIG && (window.EXAM_PREP_CONFIG.isFinalized || window.EXAM_PREP_CONFIG.isLocked));
}
