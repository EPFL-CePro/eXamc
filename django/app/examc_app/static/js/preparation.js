/* static/js/preparation.js */

(function () {
    "use strict";

    const CFG = window.EXAM_PREP_CONFIG || {};
    const URLS = CFG.urls || {};
    const CSRF = CFG.csrfToken || "";
    const EXAM_PK = CFG.examPk || "";

    const Selectors = {
        loadingModal: "#loadingModal",
        sectionList: "#prep-sections-list",
        scoringModal: "#modalScoringFormulas",
        scoringModalBody: "#modalScoringFormulasBody",
        openScoringModalBtn: ".open-scoring-formulas-modal",
        scoringForm: "#scoringFormulasForm",
        dragHandle: ".drag-handle"
    };

    function getElement(selector) {
        return document.querySelector(selector);
    }

    function getModalInstance(selector) {
        const el = getElement(selector);
        if (!el) return null;
        return bootstrap.Modal.getOrCreateInstance(el);
    }

    function showModal(selector) {
        const modal = getModalInstance(selector);
        if (modal) modal.show();
    }

    function hideModal(selector) {
        const el = getElement(selector);
        if (!el) return;

        const modal = bootstrap.Modal.getInstance(el);
        if (modal) modal.hide();
    }

    function showLoading(show) {
        const modal = getModalInstance(Selectors.loadingModal);
        if (!modal) return;

        if (show) modal.show();
        else modal.hide();
    }

    function ajaxRequest(method, url, data, {beforeSend, complete, success, error} = {}) {
        return $.ajax({
            url: url,
            type: method,
            data: data || {},
            headers: CSRF ? {"X-CSRFToken": CSRF} : {},
            beforeSend: beforeSend || function () {
                showLoading(true);
            },
            complete: complete || function () {
                showLoading(false);
            },
            success: success,
            error: error || function (xhr) {
                console.error("[preparation.js] AJAX error:", xhr);
            }
        });
    }

    function ajaxGet(url, data, callbacks) {
        return ajaxRequest("GET", url, data, callbacks);
    }

    function ajaxPost(url, data, callbacks) {
        return ajaxRequest("POST", url, data, callbacks);
    }

    function previewExam() {
        if (!URLS.previewPdf) {
            console.warn("[preparation.js] Missing previewPdf URL");
            return;
        }

        $("#exam_preview_error").hide();
        $("#exam_preview_pdf").hide();

        ajaxGet(URLS.previewPdf, {}, {
            success: function (data) {
                if (typeof data === "string" && data.endsWith(".log")) {
                    $("#exam_preview_error_message").val(data);
                    $("#exam_preview_error").show();
                } else {
                    $("#exam_preview_pdf").attr("src", data).show();
                }

                showModal("#exam_preview_dialog");
            },
            error: function (xhr) {
                console.error("[preparation.js] previewExam failed:", xhr);
            }
        });
    }

    function initSectionSortable() {
        const list = getElement(Selectors.sectionList);

        console.log("initSectionSortable", {
            listExists: !!list,
            reorderUrl: URLS.reorderSections,
            sortableExists: typeof Sortable !== "undefined"
        });

        if (!list || !URLS.reorderSections || typeof Sortable === "undefined") {
            return;
        }

        if (list._sortableInstance) {
            list._sortableInstance.destroy();
        }

        list._sortableInstance = Sortable.create(list, {
            handle: Selectors.dragHandle,
            draggable: ".sortable-section",
            animation: 150,
            onEnd: function () {
                const orderedSections = [];

                list.querySelectorAll(".sortable-section").forEach(function (card, index) {
                    const sectionId = card.dataset.sectionId;
                    const posInput = card.querySelector("input[name$='-position']");

                    if (posInput) {
                        posInput.value = index + 1;
                    }

                    orderedSections.push({
                        id: sectionId,
                        position: index + 1
                    });
                });

                fetch(URLS.reorderSections, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": CSRF
                    },
                    body: JSON.stringify({sections: orderedSections})
                })
                    .then(function (response) {
                        if (!response.ok) {
                            throw new Error("Failed to reorder sections");
                        }
                        return response.text();
                    })
                    .then(function (html) {
                        const wrapper = document.createElement("div");
                        wrapper.innerHTML = html.trim();
                        const newList = wrapper.firstElementChild;

                        if (newList) {
                            list.replaceWith(newList);
                            initSectionSortable();
                        }
                    })
                    .catch(function (error) {
                        console.error("[preparation.js] reorderSections failed:", error);
                    });
            }
        });
    }

    function getSelectedQuestionCode(typeSelect) {
        if (!typeSelect) return "";

        const selectedOption = typeSelect.options[typeSelect.selectedIndex];
        if (!selectedOption) return "";

        const selectedText = selectedOption.text.trim();
        return selectedText.split(" - ")[0].trim();
    }

    function getQuestionTypeSelectFromElement(element) {
        const questionBlock = element.closest('[id^="prep-question-"]');
        if (!questionBlock) return null;

        return questionBlock.querySelector('select[name$="question_type"]');
    }

    function updateQuestionFields(questionBar) {
        const typeSelect = questionBar.querySelector('select[name$="question_type"]');
        if (!typeSelect) return;

        const selectedCode = getSelectedQuestionCode(typeSelect);

        const randomField = questionBar.querySelector(".js-field-random");
        const maxPointsField = questionBar.querySelector(".js-field-maxpoints");
        const incrementField = questionBar.querySelector(".js-field-increment");

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

    function updateAnswerForm(answerForm) {
        const typeSelect = getQuestionTypeSelectFromElement(answerForm);
        const selectedCode = getSelectedQuestionCode(typeSelect);

        const fixPositionField = answerForm.querySelector(".js-answer-fix-position");
        const correctField = answerForm.querySelector(".js-answer-correct");
        const answerTextField = answerForm.querySelector(".js-answer-text");
        const boxTypeField = answerForm.querySelector(".js-answer-box-type");
        const boxHeightField = answerForm.querySelector(".js-answer-box-height");

        if (
            !fixPositionField ||
            !correctField ||
            !answerTextField ||
            !boxTypeField ||
            !boxHeightField
        ) {
            return;
        }

        fixPositionField.style.display = "none";
        correctField.style.display = "none";
        answerTextField.style.display = "none";
        boxTypeField.style.display = "none";
        boxHeightField.style.display = "none";

        if (selectedCode === "OPEN") {
            boxTypeField.style.display = "flex";
            boxHeightField.style.display = "flex";
        } else if (selectedCode) {
            fixPositionField.style.display = "flex";
            correctField.style.display = "flex";
            answerTextField.style.display = "flex";
        }
    }

    function bindQuestionFields(container = document) {
        const questionBars = [];

        if (container.matches && container.matches(".question-top-bar")) {
            questionBars.push(container);
        }

        if (container.querySelectorAll) {
            questionBars.push(...container.querySelectorAll(".question-top-bar"));
        }

        questionBars.forEach((questionBar) => {
            const typeSelect = questionBar.querySelector('select[name$="question_type"]');
            if (!typeSelect) return;

            updateQuestionFields(questionBar);

            if (!typeSelect.dataset.prepBound) {
                typeSelect.addEventListener("change", function () {
                    updateQuestionFields(questionBar);

                    const questionBlock = typeSelect.closest('[id^="prep-question-"]');
                    if (!questionBlock) return;

                    const answerForms = questionBlock.querySelectorAll(".js-answer-form");
                    answerForms.forEach((answerForm) => {
                        updateAnswerForm(answerForm);
                    });
                });

                typeSelect.dataset.prepBound = "1";
            }
        });
    }

    function bindAnswerForms(container = document) {
        const answerForms = [];

        if (container.matches && container.matches(".js-answer-form")) {
            answerForms.push(container);
        }

        if (container.querySelectorAll) {
            answerForms.push(...container.querySelectorAll(".js-answer-form"));
        }

        answerForms.forEach((answerForm) => {
            updateAnswerForm(answerForm);
        });
    }

    function initPreparationUI(container = document) {
        bindQuestionFields(container);
        bindAnswerForms(container);
    }

    function resizeSummernoteIframe(iframe) {
        if (!iframe) return;

        function applyResize() {
            try {
                const doc = iframe.contentDocument || iframe.contentWindow.document;
                if (!doc) return;

                const body = doc.body;
                const html = doc.documentElement;
                if (!body || !html) return;

                const newHeight = Math.max(
                    parseInt(iframe.getAttribute("height"), 10) || 180,
                    body.scrollHeight,
                    body.offsetHeight,
                    html.scrollHeight,
                    html.offsetHeight
                );

                iframe.style.height = newHeight + "px";
                iframe.setAttribute("height", newHeight);

                const wrapper = iframe.closest(".summernote-div");
                if (wrapper) {
                    wrapper.style.height = newHeight + "px";
                }
            } catch (e) {
                console.warn("Summernote resize failed", e);
            }
        }

        const attachEditorListeners = () => {
            try {
                const doc = iframe.contentDocument || iframe.contentWindow.document;
                if (!doc) return;

                doc.addEventListener("input", applyResize);
                doc.addEventListener("keyup", applyResize);
                doc.addEventListener("paste", function () {
                    setTimeout(applyResize, 0);
                });
            } catch (e) {
            }
        };

        if (iframe.contentDocument?.readyState === "complete") {
            applyResize();
            attachEditorListeners();
        } else {
            iframe.addEventListener("load", function () {
                applyResize();
                attachEditorListeners();
            }, {once: true});
        }

        setTimeout(applyResize, 50);
        setTimeout(applyResize, 150);
        setTimeout(applyResize, 300);
        setTimeout(applyResize, 600);
    }

    function resizeAllSummernoteIframes(container = document) {
        container.querySelectorAll(".summernote-div iframe").forEach((iframe) => {
            resizeSummernoteIframe(iframe);
        });
    }

    const ScoringFormulasModal = {
        get body() {
            return getElement(Selectors.scoringModalBody);
        },

        setBody(html) {
            if (this.body) {
                this.body.innerHTML = html;
            }
        },

        renderError(message) {
            this.setBody(
                `<div class="alert alert-danger mb-0">${message || "Unable to load formulas."}</div>`
            );
        },

        buildParams(button) {
            return {
                exam_pk: button.dataset.examPk || EXAM_PK || "",
                prep_section: button.dataset.prepSection || "",
                prep_question: button.dataset.prepQuestion || "",
                prep_answer: button.dataset.prepAnswer || ""
            };
        },

        open(params) {
            if (!URLS.scoringFormulasModal) {
                console.warn("[preparation.js] Missing scoringFormulasModal URL");
                this.renderError("Configuration error: missing modal URL.");
                showModal(Selectors.scoringModal);
                return;
            }

            if (!params.exam_pk) {
                this.renderError("Missing exam_pk.");
                showModal(Selectors.scoringModal);
                return;
            }

            ajaxGet(URLS.scoringFormulasModal, params, {
                success: (html) => {
                    this.setBody(html);

                    const toggleBtn = document.getElementById("toggleScoringHelp");
                    if (toggleBtn) {
                        toggleBtn.innerHTML = '<i class="fa-solid fa-circle-question fa-2x" style="color: rgb(0, 62, 173);"></i>';
                    }
                    showModal(Selectors.scoringModal);
                },
                error: (xhr) => {
                    console.error("[preparation.js] open scoring formulas modal failed:", xhr);
                    this.renderError("Unable to load formulas.");
                    showModal(Selectors.scoringModal);
                }
            });
        },

        submit(form) {
            ajaxPost(form.action, $(form).serialize(), {
                success: (response) => {
                    if (response.success) {
                        hideModal(Selectors.scoringModal);

                        if (response.message) {
                            window.alert(response.message);
                        }
                        return;
                    }

                    if (response.html) {
                        this.setBody(response.html);
                        return;
                    }

                    this.renderError(response.message || "Unable to save formulas.");
                },
                error: (xhr) => {
                    console.error("[preparation.js] save scoring formulas failed:", xhr);

                    if (xhr.responseJSON && xhr.responseJSON.html) {
                        this.setBody(xhr.responseJSON.html);
                        return;
                    }

                    this.renderError("An error occurred while saving formulas.");
                }
            });
        },

        updateRowIndexes() {
            const rows = document.querySelectorAll("#scoringFormulasTableBody .scoring-formula-row");
            rows.forEach((row, index) => {
                const indexCell = row.querySelector(".scoring-row-index");
                if (!indexCell) return;

                const hiddenIdInput = indexCell.querySelector('input[type="hidden"]');
                indexCell.firstChild.textContent = (index + 1) + " ";

                if (hiddenIdInput) {
                    indexCell.appendChild(hiddenIdInput);
                }
            });
        },

        removeEmptyMessageRow() {
            const emptyRow = document.querySelector(".no-scoring-formulas-row");
            if (emptyRow) {
                emptyRow.remove();
            }
        },

        addRow() {
            const template = document.getElementById("emptyScoringFormulaRowTemplate");
            const tbody = document.getElementById("scoringFormulasTableBody");
            const totalFormsInput = document.getElementById("id_form-TOTAL_FORMS");

            if (!template || !tbody || !totalFormsInput) {
                console.warn("[preparation.js] Missing template, tbody, or TOTAL_FORMS input.");
                return;
            }

            const formIndex = parseInt(totalFormsInput.value, 10);
            let html = template.innerHTML.replace(/__prefix__/g, formIndex);
            html = html.replace(/__index__/g, formIndex + 1);

            this.removeEmptyMessageRow();
            tbody.insertAdjacentHTML("beforeend", html);

            totalFormsInput.value = formIndex + 1;
            this.updateRowIndexes();
        },

        removeUnsavedRow(button) {
            const row = button.closest(".scoring-formula-row");
            const tbody = document.getElementById("scoringFormulasTableBody");
            const totalFormsInput = document.getElementById("id_form-TOTAL_FORMS");

            if (!row || !tbody || !totalFormsInput) return;

            row.remove();

            const rows = tbody.querySelectorAll(".scoring-formula-row");
            totalFormsInput.value = rows.length;

            rows.forEach((currentRow, index) => {
                currentRow.querySelectorAll("input, select, textarea, label").forEach((el) => {
                    if (el.name) {
                        el.name = el.name.replace(/form-\d+-/g, `form-${index}-`);
                    }
                    if (el.id) {
                        el.id = el.id.replace(/id_form-\d+-/g, `id_form-${index}-`);
                    }
                    if (el.htmlFor) {
                        el.htmlFor = el.htmlFor.replace(/id_form-\d+-/g, `id_form-${index}-`);
                    }
                });
            });

            this.updateRowIndexes();

            if (!tbody.querySelector(".scoring-formula-row")) {
                tbody.innerHTML = `
        <tr class="no-scoring-formulas-row">
          <td colspan="4" class="text-center">No formulas found.</td>
        </tr>
      `;
            }
        },

        reloadFromCurrentForm() {
            const form = document.getElementById("scoringFormulasForm");
            if (!form) return;

            const prepSection = form.querySelector('input[name="prep_section"]')?.value || "";
            const prepQuestion = form.querySelector('input[name="prep_question"]')?.value || "";
            const prepAnswer = form.querySelector('input[name="prep_answer"]')?.value || "";

            this.open({
                exam_pk: EXAM_PK || "",
                prep_section: prepSection,
                prep_question: prepQuestion,
                prep_answer: prepAnswer
            });
        },

        deleteSavedRow(deleteUrl) {
            if (!deleteUrl) return;

            const confirmed = window.confirm("Delete this scoring?");
            if (!confirmed) return;

            ajaxPost(deleteUrl, {}, {
                success: (response) => {
                    if (response.success) {
                        this.reloadFromCurrentForm();
                        return;
                    }

                    this.renderError(response.message || "Unable to delete formula.");
                },
                error: (xhr) => {
                    console.error("[preparation.js] delete scoring formula failed:", xhr);
                    this.renderError("An error occurred while deleting formula.");
                }
            });
        },

        bindEvents() {
            document.addEventListener("click", (event) => {
                const addButton = event.target.closest("#addScoringFormulaRow");
                if (addButton) {
                    event.preventDefault();
                    this.addRow();
                    return;
                }

                const removeUnsavedButton = event.target.closest(".remove-scoring-formula-row");
                if (removeUnsavedButton) {
                    event.preventDefault();
                    this.removeUnsavedRow(removeUnsavedButton);
                    return;
                }

                const deleteSavedButton = event.target.closest(".delete-scoring-formula-row");
                if (deleteSavedButton) {
                    event.preventDefault();
                    this.deleteSavedRow(deleteSavedButton.dataset.deleteUrl);
                    return;
                }

                const toggleHelpButton = event.target.closest("#toggleScoringHelp");
                if (toggleHelpButton) {
                    event.preventDefault();

                    const helpPanel = document.getElementById("scoringHelpPanel");
                    if (!helpPanel) return;

                    helpPanel.classList.toggle("open");
                    toggleHelpButton.innerHTML = helpPanel.classList.contains("open")
                        ? '<i class="fa-solid fa-circle-xmark fa-2x" style="color: rgb(0, 62, 173);"></i>'
                        : '<i class="fa-solid fa-circle-question fa-2x" style="color: rgb(0, 62, 173);"></i>';
                    return;
                }

                const button = event.target.closest(Selectors.openScoringModalBtn);
                if (!button) return;

                event.preventDefault();
                this.open(this.buildParams(button));
            });

            document.addEventListener("submit", (event) => {
                const form = event.target.closest(Selectors.scoringForm);
                if (!form) return;

                event.preventDefault();
                this.submit(form);
            });
        }


    };

    document.addEventListener("click", function (event) {
        const handle = event.target.closest(Selectors.dragHandle);
        if (handle) {
            event.stopPropagation();
        }
    });

    document.body.addEventListener("htmx:configRequest", function (event) {
        if (typeof CSRF !== "undefined" && CSRF) {
            event.detail.headers["X-CSRFToken"] = CSRF;
        }
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
        initSectionSortable();
        initPreparationUI(event.target);
        resizeAllSummernoteIframes(event.target);
    });

    document.addEventListener("shown.bs.collapse", function (event) {
        resizeAllSummernoteIframes(event.target);
    });

    document.addEventListener("DOMContentLoaded", function () {
        initSectionSortable();
        ScoringFormulasModal.bindEvents();
        initPreparationUI(document);
        resizeAllSummernoteIframes(document);
    });

    window.preview_exam = previewExam;
})
();