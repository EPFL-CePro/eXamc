// Fields of a question / answer form shown according to the question type

function matchingElements(container: Document | Element, selector: string): HTMLElement[] {
    const elements: HTMLElement[] = [];

    if (container instanceof Element && container.matches(selector)) {
        elements.push(container as HTMLElement);
    }

    elements.push(...container.querySelectorAll<HTMLElement>(selector));

    return elements;
}

function getSelectedQuestionCode(typeSelect: HTMLSelectElement | null): string {
    if (!typeSelect) return "";

    const selectedOption = typeSelect.options[typeSelect.selectedIndex];
    if (!selectedOption) return "";

    const selectedText = selectedOption.text.trim();
    return (selectedText.split(" - ")[0] ?? "").trim();
}

function getQuestionTypeSelectFromElement(element: Element): HTMLSelectElement | null {
    const questionBlock = element.closest('[id^="prep-question-"]');
    if (!questionBlock) return null;

    return questionBlock.querySelector<HTMLSelectElement>('select[name$="question_type"]');
}

function updateQuestionFields(questionBar: HTMLElement): void {
    const typeSelect = questionBar.querySelector<HTMLSelectElement>('select[name$="question_type"]');
    if (!typeSelect) return;

    const selectedCode = getSelectedQuestionCode(typeSelect);

    // An open question is scored by its corrector boxes: no scoring formula
    const scoring = questionBar.closest('[id^="prep-question-"]')?.querySelector<HTMLElement>(".js-question-scoring");
    if (scoring) scoring.style.display = selectedCode === "OPEN" ? "none" : "";

    const randomField = questionBar.querySelector<HTMLElement>(".js-field-random");
    const maxPointsField = questionBar.querySelector<HTMLElement>(".js-field-maxpoints");
    const incrementField = questionBar.querySelector<HTMLElement>(".js-field-increment");

    if (!randomField || !maxPointsField || !incrementField) return;

    randomField.style.display = "none";
    maxPointsField.style.display = "none";
    incrementField.style.display = "none";

    if (selectedCode === "OPEN") {
        maxPointsField.style.display = "flex";
        incrementField.style.display = "flex";
    } else if (selectedCode === "TF") {
        // show none
    } else if (selectedCode) {
        randomField.style.display = "flex";
    }
}

function updateAnswerForm(answerForm: HTMLElement): void {
    const typeSelect = getQuestionTypeSelectFromElement(answerForm);
    const selectedCode = getSelectedQuestionCode(typeSelect);

    const scoring = answerForm.closest('[id^="prep-answer-"]')?.querySelector<HTMLElement>(".js-answer-scoring");
    if (scoring) scoring.style.display = selectedCode === "OPEN" ? "none" : "";

    const correctField = answerForm.querySelector<HTMLElement>(".js-answer-correct");
    const answerTextField = answerForm.querySelector<HTMLElement>(".js-answer-text");
    const boxTypeField = answerForm.querySelector<HTMLElement>(".js-answer-box-type");
    const boxHeightField = answerForm.querySelector<HTMLElement>(".js-answer-box-height");

    if (!correctField || !answerTextField || !boxTypeField || !boxHeightField) {
        return;
    }

    correctField.style.display = "none";
    answerTextField.style.display = "none";
    boxTypeField.style.display = "none";
    boxHeightField.style.display = "none";

    if (selectedCode === "OPEN") {
        boxTypeField.style.display = "flex";
        boxHeightField.style.display = "flex";
    } else if (selectedCode) {
        correctField.style.display = "flex";
        answerTextField.style.display = "flex";
    }
}

function bindQuestionFields(container: Document | Element): void {
    matchingElements(container, ".question-top-bar").forEach((questionBar) => {
        const typeSelect = questionBar.querySelector<HTMLSelectElement>('select[name$="question_type"]');
        if (!typeSelect) return;

        updateQuestionFields(questionBar);

        if (!typeSelect.dataset["prepBound"]) {
            typeSelect.addEventListener("change", () => {
                updateQuestionFields(questionBar);

                const questionBlock = typeSelect.closest('[id^="prep-question-"]');
                if (!questionBlock) return;

                questionBlock.querySelectorAll<HTMLElement>(".js-answer-form").forEach(updateAnswerForm);
            });

            typeSelect.dataset["prepBound"] = "1";
        }
    });
}

function bindAnswerForms(container: Document | Element): void {
    matchingElements(container, ".js-answer-form").forEach(updateAnswerForm);
}

export function initPreparationUI(container: Document | Element = document): void {
    bindQuestionFields(container);
    bindAnswerForms(container);
}
