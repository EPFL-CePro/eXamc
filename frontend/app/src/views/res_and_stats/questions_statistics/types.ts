/** Answers distribution of a multiple-choice or true/false question (bar chart). */
export interface McqChart {
    canvasId: string;
    /** The answers ("None" when nothing was ticked). */
    labels: string[];
    /** Share of the students who gave each answer, in %. */
    rates: number[];
    /** Number of students who gave each answer. */
    quantities: number[];
}

/** Points distribution of an open question, by quarter of its max points (stacked horizontal bar). */
export interface OpenChart {
    canvasId: string;
    quarters: { maxPoints: number; students: number }[];
}

/** Answers distribution of a common question in one of the common exams (bar chart). */
export interface ByExamChart {
    canvasId: string;
    /** " <percent>% - <answer>" per answer. */
    labels: string[];
    percents: number[];
}

/** Data of every chart of the page (questions-stats-charts json_script). */
export interface QuestionsStatsCharts {
    presentStudents: number;
    mcq: McqChart[];
    open: OpenChart[];
    byExam: ByExamChart[];
}