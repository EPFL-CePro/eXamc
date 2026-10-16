import type { SortableInstance, SortableOptions } from "@examc/types/definitions/sortable";

import { CSRF, isExamFinalized, Selectors, URLS } from "./config.ts";
import { getElement } from "./ajax.ts";
import { initMarkdownEditors } from "./markdown-editors.ts";
import { initPreparationUI } from "./question-fields.ts";

type OrderedItem = { id: string | undefined; position: number };

/** The Sortable instance of each list, destroyed before the list is set up again. */
const instances = new WeakMap<HTMLElement, SortableInstance>();

function replaceInstance(list: HTMLElement, options: SortableOptions): void {
    instances.get(list)?.destroy();
    instances.set(list, Sortable.create(list, options));
}

/** POSTs the new order and returns the HTML the server sends back (the re-rendered list). */
async function postOrder(url: string, key: string, items: OrderedItem[], errorMessage: string): Promise<Element | null> {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": CSRF,
        },
        body: JSON.stringify({ [key]: items }),
    });
    if (!response.ok) throw new Error(errorMessage);

    const wrapper = document.createElement("div");
    wrapper.innerHTML = (await response.text()).trim();
    return wrapper.firstElementChild;
}

function reinitAll(): void {
    initSectionSortable();
    initQuestionSortable();
    initAnswerSortable();
    initPreparationUI(document);
    initMarkdownEditors(document);
}

export function initSectionSortable(): void {
    const list = getElement(Selectors.sectionList);

    if (!list || !URLS.reorderSections || typeof Sortable === "undefined" || isExamFinalized()) {
        return;
    }

    replaceInstance(list, {
        handle: Selectors.dragHandle,
        draggable: ".sortable-section",
        animation: 150,
        onEnd: () => {
            const orderedSections: OrderedItem[] = [];

            list.querySelectorAll<HTMLElement>(".sortable-section").forEach((card, index) => {
                const posInput = card.querySelector<HTMLInputElement>("input[name$='-position']");

                if (posInput) {
                    posInput.value = String(index + 1);
                }

                orderedSections.push({ id: card.dataset["sectionId"], position: index + 1 });
            });

            postOrder(URLS.reorderSections, "sections", orderedSections, "Failed to reorder sections")
                .then((newList) => {
                    if (newList) {
                        list.replaceWith(newList);
                        initSectionSortable();
                        initPreparationUI(newList);
                        initMarkdownEditors(newList);
                    }
                })
                .catch((error: unknown) => {
                    console.error("[preparation] reorderSections failed:", error);
                });
        },
    });
}

export function initQuestionSortable(): void {
    if (typeof Sortable === "undefined" || isExamFinalized()) {
        return;
    }

    document.querySelectorAll<HTMLElement>('[id^="prep-questions-list-"]').forEach((list) => {
        const sectionCard = list.closest<HTMLElement>(".sortable-section");
        const sectionId = sectionCard ? sectionCard.dataset["sectionId"] : null;
        if (!sectionId || !URLS.reorderQuestionsTemplate) return;

        replaceInstance(list, {
            handle: Selectors.dragHandle,
            draggable: ".sortable-question",
            animation: 150,
            onEnd: () => {
                const orderedQuestions: OrderedItem[] = [];

                list.querySelectorAll<HTMLElement>(".sortable-question").forEach((card, index) => {
                    orderedQuestions.push({ id: card.dataset["questionId"], position: index + 1 });
                });

                const url = URLS.reorderQuestionsTemplate.replace("__SECTION_ID__", sectionId);

                postOrder(url, "questions", orderedQuestions, "Failed to reorder questions")
                    .then((newList) => {
                        if (newList) {
                            list.replaceWith(newList);
                            reinitAll();
                        }
                    })
                    .catch((error: unknown) => {
                        console.error("[preparation] reorderQuestions failed:", error);
                    });
            },
        });
    });
}

export function initAnswerSortable(): void {
    if (typeof Sortable === "undefined" || isExamFinalized()) {
        return;
    }

    document.querySelectorAll<HTMLElement>('[id^="prep-answers-list-"]').forEach((list) => {
        const questionId = list.dataset["questionId"];
        if (!questionId || !URLS.reorderAnswersTemplate) return;

        replaceInstance(list, {
            handle: Selectors.dragHandle,
            draggable: ".sortable-answer-wrapper",
            animation: 150,
            onEnd: () => {
                const orderedAnswers: OrderedItem[] = [];

                list.querySelectorAll<HTMLElement>(".sortable-answer-wrapper").forEach((card, index) => {
                    orderedAnswers.push({ id: card.dataset["answerId"], position: index + 1 });
                });

                const url = URLS.reorderAnswersTemplate.replace("__QUESTION_ID__", questionId);

                postOrder(url, "answers", orderedAnswers, "Failed to reorder answers")
                    .then((newBlock) => {
                        const target = document.getElementById(`answers-containers-${questionId}`);
                        if (newBlock && target) {
                            target.replaceWith(newBlock);
                            reinitAll();
                        }
                    })
                    .catch((error: unknown) => {
                        console.error("[preparation] reorderAnswers failed:", error);
                    });
            },
        });
    });
}
