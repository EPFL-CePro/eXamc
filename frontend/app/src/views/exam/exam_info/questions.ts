import { byId } from '@examc/helpers/dom.ts';
import { postText } from '@examc/helpers/http.ts';
import { LoadingModal } from '@examc/modals';

import { showRequestError } from './exam.ts';

/** Set before reloading after a questions update: remind to regenerate the stats, at the same scroll position. */
const REGEN_KEY = 'examc:exam-info:regen-stats';
const SCROLL_KEY = 'examc:exam-info:scroll';

interface QuestionsConfig {
    form: HTMLFormElement;
    url: string;
    csrfToken: string;
    examPk: string;
}

/** One question as update_questions reads it (keys are the old table's header texts). */
interface QuestionData {
    Question: string;
    Type?: number;
    Answers?: string;
    'Max Points': string;
    Common?: boolean;
}

/**
 * Reads the questions table.
 *
 * @param {HTMLFormElement} form - The questions form.
 * @return {QuestionData[]} One entry per question.
 */
function readQuestions(form: HTMLFormElement): QuestionData[] {
    return [...form.querySelectorAll<HTMLTableRowElement>('tr[data-question]')].map((row) => {
        const id = row.dataset['question'] ?? '';
        const input = (selector: string): HTMLInputElement | null => row.querySelector<HTMLInputElement>(selector);

        const data: QuestionData = {
            Question: id,
            'Max Points': input(`input[name="max-points-${id}"]`)?.value ?? '',
        };

        const type = input(`input[name="type-${id}"]:checked`);
        if (type) data.Type = Number(type.value); // position of the type, from 1

        const answers = input(`input[name="answers-${id}"]`);
        if (answers) data.Answers = answers.value;

        const common = input(`input[name="common-${id}"]`);
        if (common) data.Common = common.checked;

        return data;
    });
}

/** Shows each answers slider's value beside it. */
function syncOutputs(form: HTMLFormElement): void {
    for (const output of form.querySelectorAll<HTMLOutputElement>('output[for]')) {
        const range = form.querySelector<HTMLInputElement>(`#${CSS.escape(output.htmlFor.value)}`);
        if (range) output.value = range.value;
    }
}

export function initQuestions({ form, url, csrfToken, examPk }: QuestionsConfig): void {
    // Back from a questions update
    if (sessionStorage.getItem(REGEN_KEY) === examPk) {
        byId('regen-stats-alert').hidden = false;
        const scroll = Number(sessionStorage.getItem(SCROLL_KEY));
        if (scroll) window.scrollTo(0, scroll);
    }
    sessionStorage.removeItem(REGEN_KEY);
    sessionStorage.removeItem(SCROLL_KEY);

    form.addEventListener('input', () => syncOutputs(form));
    form.addEventListener('reset', () => setTimeout(() => syncOutputs(form))); // values are reset after the event

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        const data = JSON.stringify(readQuestions(form), null, 2);

        void (async () => {
            try {
                await new LoadingModal(() => postText(url, { csrfmiddlewaretoken: csrfToken, data })).result;
                sessionStorage.setItem(REGEN_KEY, examPk);
                sessionStorage.setItem(SCROLL_KEY, String(window.scrollY));
                window.location.href = `${window.location.pathname}?dataUpdated=true`;
            } catch (error) {
                showRequestError(error, 'The questions could not be saved.');
            }
        })();
    });
}