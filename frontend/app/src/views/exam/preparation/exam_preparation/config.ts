import { requireData } from "@examc/helpers/dom.ts";

/** URLs given by the template (exam_preparation.html). Use the functions below for those with an id. */
export interface ExamPrepUrls {
    previewStart: string;
    reorderSections: string;
    scoringFormulasModal: string;
    editLatexFile: string;
    saveLatexFile: string;
    editLatexPackages: string;
    saveLatexPackages: string;
    generateFinalStart: string;
    cancelFinal: string;
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

/** The configuration of the page is in the data attributes of #prep-root. */
const root = document.getElementById("prep-root");
if (!root) throw new Error("#prep-root not found");

function readConfig(root: HTMLElement): ExamPrepConfig {
    return {
        csrfToken: requireData(root, "csrfToken"),
        examPk: requireData(root, "examPk"),
        isFinalized: requireData(root, "isFinalized") === "true",
        isLocked: requireData(root, "isLocked") === "true",
        // Empty when no generation is running
        activeFinalTaskId: root.dataset["activeFinalTaskId"] ?? "",
        activeFinalStartedAt: root.dataset["activeFinalStartedAt"] ?? "",
        urls: {
            previewStart: requireData(root, "previewStartUrl"),
            reorderSections: requireData(root, "reorderSectionsUrl"),
            scoringFormulasModal: requireData(root, "scoringFormulasModalUrl"),
            editLatexFile: requireData(root, "editLatexFileUrl"),
            saveLatexFile: requireData(root, "saveLatexFileUrl"),
            editLatexPackages: requireData(root, "editLatexPackagesUrl"),
            saveLatexPackages: requireData(root, "saveLatexPackagesUrl"),
            generateFinalStart: requireData(root, "generateFinalStartUrl"),
            cancelFinal: requireData(root, "cancelFinalUrl"),
        },
    };
}

export const CFG: ExamPrepConfig = readConfig(root);
export const URLS: ExamPrepUrls = CFG.urls;
export const CSRF: string = CFG.csrfToken;
export const EXAM_PK: string = CFG.examPk;

/** The URLs of the template, given with the id 0 at their end. */
const ID_URLS = {
    previewStatus: requireData(root, "previewStatusUrl"),
    reorderQuestions: requireData(root, "reorderQuestionsUrl"),
    reorderAnswers: requireData(root, "reorderAnswersUrl"),
    celeryTaskStatus: requireData(root, "celeryTaskStatusUrl"),
};

function withId(url: string, id: string): string {
    return url.replace(/\/0\/?$/, (end) => `/${id}${end.endsWith("/") ? "/" : ""}`);
}

export const previewStatusUrl = (jobId: string): string => withId(ID_URLS.previewStatus, jobId);
export const reorderQuestionsUrl = (sectionId: string): string => withId(ID_URLS.reorderQuestions, sectionId);
export const reorderAnswersUrl = (questionId: string): string => withId(ID_URLS.reorderAnswers, questionId);
export const celeryTaskStatusUrl = (taskId: string): string => ID_URLS.celeryTaskStatus.replace("TASK_ID_PLACEHOLDER", taskId);

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
    return CFG.isFinalized || CFG.isLocked;
}
