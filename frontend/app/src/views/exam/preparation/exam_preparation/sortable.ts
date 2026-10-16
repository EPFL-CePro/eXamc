import type { SortableInstance, SortableOptions } from "@examc/types/definitions/sortable";

import { CSRF, isExamFinalized, reorderAnswersUrl, reorderQuestionsUrl, Selectors, URLS } from "./config.ts";
import { getElement, processHtmx } from "./ajax.ts";
import { initMarkdownEditors } from "./markdown-editors.ts";
import { initPreparationUI } from "./question-fields.ts";
import { withSavingOverlay } from "./saving-overlay.ts";

type OrderedItem = { id: string | undefined; position: number };

/** The Sortable instance of each list, destroyed before the list is set up again. */
const instances = new WeakMap<HTMLElement, SortableInstance>();

function replaceInstance(list: HTMLElement, options: SortableOptions): void {
    instances.get(list)?.destroy();
    instances.set(list, Sortable.create(list, options));
}

/** POSTs the new order behind the saving overlay and returns the HTML the server sends back (the re-rendered list). */
async function postOrder(url: string, key: string, items: OrderedItem[], errorMessage: string): Promise<string> {
    return withSavingOverlay(async () => {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": CSRF,
            },
            body: JSON.stringify({ [key]: items }),
        });
        if (!response.ok) throw new Error(errorMessage);

        return (await response.text()).trim();
    });
}

/** The first element of an HTML snippet. */
function firstElement(html: string): Element | null {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html;
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

    if (!list || typeof Sortable === "undefined" || isExamFinalized()) {
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
                .then((html) => {
                    const newList = firstElement(html);
                    if (newList) {
                        list.replaceWith(newList);
                        processHtmx(newList);
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
        if (!sectionId) return;

        replaceInstance(list, {
            handle: Selectors.dragHandle,
            draggable: ".sortable-question",
            animation: 150,
            onEnd: () => {
                const orderedQuestions: OrderedItem[] = [];

                list.querySelectorAll<HTMLElement>(".sortable-question").forEach((card, index) => {
                    orderedQuestions.push({ id: card.dataset["questionId"], position: index + 1 });
                });

                const url = reorderQuestionsUrl(sectionId);

                postOrder(url, "questions", orderedQuestions, "Failed to reorder questions")
                    .then((html) => {
                        // The response is the content of the list: a placeholder by question, that htmx loads
                        list.innerHTML = html;
                        processHtmx(list);
                        reinitAll();
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
        if (!questionId) return;

        replaceInstance(list, {
            handle: Selectors.dragHandle,
            draggable: ".sortable-answer-wrapper",
            animation: 150,
            onEnd: () => {
                const orderedAnswers: OrderedItem[] = [];

                list.querySelectorAll<HTMLElement>(".sortable-answer-wrapper").forEach((card, index) => {
                    orderedAnswers.push({ id: card.dataset["answerId"], position: index + 1 });
                });

                const url = reorderAnswersUrl(questionId);

                postOrder(url, "answers", orderedAnswers, "Failed to reorder answers")
                    .then((html) => {
                        const newBlock = firstElement(html);
                        const target = document.getElementById(`answers-containers-${questionId}`);
                        if (newBlock && target) {
                            target.replaceWith(newBlock);
                            processHtmx(newBlock);
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
