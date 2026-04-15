/* static/js/preparation.js */

(function () {
    "use strict";

    const CFG = window.EXAM_PREP_CONFIG || {};
    const URLS = CFG.urls || {};
    const CSRF = CFG.csrfToken || "";
    const EXAM_PK = CFG.examPk || "";

    function isExamFinalized() {
        return !!(window.EXAM_PREP_CONFIG && window.EXAM_PREP_CONFIG.isFinalized);
    }

    const Selectors = {
        loadingModal: "#loadingModal",
        sectionList: "#prep-sections-list",
        scoringModal: "#modalScoringFormulas",
        scoringModalBody: "#modalScoringFormulasBody",
        openScoringModalBtn: ".open-scoring-formulas-modal",
        scoringForm: "#scoringFormulasForm",
        dragHandle: ".drag-handle"
    };

    const markdownEditors = new Map();
    let markdownEditorSeq = 0;

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

    let currentGenFinalJobId = null;
    let genFinalPollingTimer = null;
    let genFinalWasSuccessful = false;

    function resetGenFinalUi() {
        console.log("resetGenFinalUi called");
        $("#generate_final_loading").hide();
        $("#generate_final_error").hide();
        $("#generate_final_success").hide().html("");
    }

    function setGenFinalLoading(isLoading) {
        if (isLoading) {
            $("#generate_final_loading").show();
        } else {
            $("#generate_final_loading").hide();
        }
    }

    function showGenFinalError(message) {
        $("#generate_final_error_message").val(message || "Error during final files generation.");
        $("#generate_final_error").show();
        $("#generate_final_loading").hide();
    }

    function showGenFinalSuccess(data) {
        console.log("showGenFinalSuccess called");

        const $success = $("#generate_final_exam_files_dialog #generate_final_success");
        console.log("before show:", $success.attr("style"));

        genFinalWasSuccessful = true;

        $("#generate_final_loading").hide();
        $("#generate_final_error").hide();

        const summary = data.summary || {};
        const resultHtml = `
            <div class="alert alert-success">Final exam generated successfully.</div>
            <div class="mb-3">
                <strong>Build ID:</strong> ${data.build_id || "-"}<br>
                <strong>Pages:</strong> ${summary.pages || 0}<br>
                <strong>Boxes:</strong> ${summary.boxes || 0}<br>
                <strong>Marks:</strong> ${summary.marks || 0}<br>
                <strong>Zones:</strong> ${summary.zones || 0}<br>
                <strong>Digits:</strong> ${summary.digits || 0}<br>
                <strong>Unknown payloads:</strong> ${summary.unknown_payloads || 0}
            </div>
            <div class="d-flex gap-2 flex-wrap">
                ${data.subject_pdf_path ? `<a class="btn btn-primary btn-sm" href="${data.subject_pdf_path}" target="_blank">Open subject PDF</a>` : ""}
                ${data.catalog_pdf_path ? `<a class="btn btn-outline-primary btn-sm" href="${data.catalog_pdf_path}" target="_blank">Open catalog PDF</a>` : ""}
            </div>
        `;

        $("#generate_final_success").html(resultHtml).show();

        $success.html(resultHtml).css("display", "block");

        console.log("after show:", $success.attr("style"));

        setTimeout(function () {
            console.log("500ms later:", $("#generate_final_exam_files_dialog #generate_final_success").attr("style"));
        }, 500);
    }

    function stopGenFinalPolling() {
        if (genFinalPollingTimer) {
            clearTimeout(genFinalPollingTimer);
            genFinalPollingTimer = null;
        }
    }

    function generateFinalExamFiles() {
        if (!URLS.generateFinalStart) {
            console.warn("[preparation.js] Missing generateFinalStart URL");
            return;
        }

        genFinalWasSuccessful = false;

        stopGenFinalPolling();
        resetGenFinalUi();
        setGenFinalLoading(true);
        showModal("#generate_final_exam_files_dialog");

        ajaxGet(URLS.generateFinalStart, {}, {
            success: function (data) {
                if (!data.job_id) {
                    showGenFinalError("Impossible to start final exam files generation.");
                    return;
                }

                currentGenFinalJobId = data.job_id;
                pollGenFinalStatus(data.job_id);
            },
            error: function (xhr) {
                let message = "Error starting final exam files generation.";
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    message = xhr.responseJSON.error;
                } else if (xhr.responseText) {
                    message = xhr.responseText;
                }
                showGenFinalError(message);
            }
        });
    }

    function pollGenFinalStatus(jobId, attempt = 0) {
        const maxAttempts = 60;
        const url = URLS.generateFinalStatus.replace("__JOB_ID__", jobId);

        if (attempt >= maxAttempts) {
            showGenFinalError("Generation took to much time or worker is blocked");
            return;
        }

        ajaxGet(url, {}, {
            success: function (data) {
                if (data.status === "pending" || data.status === "running") {
                    setGenFinalLoading(true);
                    genFinalPollingTimer = setTimeout(function () {
                        pollGenFinalStatus(jobId, attempt + 1);
                    }, 1000);
                    return;
                }

                if (data.status === "error") {
                    showGenFinalError(data.error || "Error during generation.");
                    return;
                }

                if (data.status === "success" ) {
                    stopGenFinalPolling();
                    showGenFinalSuccess(data);
                    return;
                }

                showGenFinalError("Generation status unattended.");
            },
            error: function () {
                showGenFinalError("Error getting status.");
            }
        });
    }

    // AMC - generate final exam files
    let currentPreviewJobId = null;
    let previewPollingTimer = null;

    function resetPreviewUi() {
        $("#exam_preview_loading").hide();
        $("#exam_preview_error").hide();
        $("#exam_preview_pdf").hide().attr("src", "");
    }

    function setPreviewLoading(isLoading) {
        if (isLoading) {
            $("#exam_preview_loading").show();
        } else {
            $("#exam_preview_loading").hide();
        }
    }

    function showPreviewError(message) {
        $("#exam_preview_error_message").val(message || "Error during preview generation.");
        $("#exam_preview_error").show();
        $("#exam_preview_pdf").hide();
        $("#exam_preview_loading").hide();
    }

    function showPreviewPdf(pdfUrl) {
        $("#exam_preview_pdf").attr("src", pdfUrl).show();
        $("#exam_preview_error").hide();
        $("#exam_preview_loading").hide();
    }

    function stopPreviewPolling() {
        if (previewPollingTimer) {
            clearTimeout(previewPollingTimer);
            previewPollingTimer = null;
        }
    }

    function previewExam() {
        if (!URLS.previewStart) {
            console.warn("[preparation.js] Missing previewStart URL");
            return;
        }

        stopPreviewPolling();
        resetPreviewUi();
        setPreviewLoading(true);
        showModal("#exam_preview_dialog");

        ajaxGet(URLS.previewStart, {}, {
            success: function (data) {
                if (!data.job_id) {
                    showPreviewError("Impossible to start preview.");
                    return;
                }

                currentPreviewJobId = data.job_id;
                pollPreviewStatus(data.job_id);
            },
            error: function (xhr) {
                let message = "Error starting preview.";
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    message = xhr.responseJSON.error;
                } else if (xhr.responseText) {
                    message = xhr.responseText;
                }
                showPreviewError(message);
            }
        });
    }

    function pollPreviewStatus(jobId, attempt = 0) {
        const maxAttempts = 60;
        const url = URLS.previewStatus.replace("__JOB_ID__", jobId);

        if (attempt >= maxAttempts) {
            showPreviewError("Le preview prend trop de temps ou le worker est bloqué.");
            return;
        }

        ajaxGet(url, {}, {
            success: function (data) {
                if (data.status === "pending" || data.status === "running") {
                    setPreviewLoading(true);
                    previewPollingTimer = setTimeout(function () {
                        pollPreviewStatus(jobId, attempt + 1);
                    }, 1000);
                    return;
                }

                if (data.status === "error") {
                    showPreviewError(data.error || "Erreur de compilation.");
                    return;
                }

                if (data.status === "success" && data.pdf_url) {
                    showPreviewPdf(data.pdf_url);
                    return;
                }

                showPreviewError("Statut de preview inattendu.");
            },
            error: function () {
                showPreviewError("Erreur lors de la récupération du statut.");
            }
        });
    }

    function openUnlockEditingModal() {
        showModal("#unlock_exam_editing_modal");
    }

    function confirmUnlockEditing() {
        const form = document.getElementById("unlockExamEditingForm");
        if (form) {
            form.submit();
        }
    }


    function initSectionSortable() {
        const list = getElement(Selectors.sectionList);

        if (!list || !URLS.reorderSections || typeof Sortable === "undefined" || isExamFinalized()) {
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
                            initPreparationUI(newList);
                            initMarkdownEditors(newList);
                        }
                    })
                    .catch(function (error) {
                        console.error("[preparation.js] reorderSections failed:", error);
                    });
            }
        });
    }

    function initQuestionSortable() {
        if (typeof Sortable === "undefined" || isExamFinalized()) {
            return;
        }

        document.querySelectorAll('[id^="prep-questions-list-"]').forEach(function (list) {
            const sectionCard = list.closest(".sortable-section");
            const sectionId = sectionCard ? sectionCard.dataset.sectionId : null;
            if (!sectionId || !URLS.reorderQuestionsTemplate) return;

            if (list._sortableInstance) {
                list._sortableInstance.destroy();
            }

            list._sortableInstance = Sortable.create(list, {
                handle: Selectors.dragHandle,
                draggable: ".sortable-question",
                animation: 150,
                onEnd: function () {
                    const orderedQuestions = [];

                    list.querySelectorAll(".sortable-question").forEach(function (card, index) {
                        orderedQuestions.push({
                            id: card.dataset.questionId,
                            position: index + 1
                        });
                    });

                    const url = URLS.reorderQuestionsTemplate.replace("__SECTION_ID__", sectionId);

                    fetch(url, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": CSRF
                        },
                        body: JSON.stringify({ questions: orderedQuestions })
                    })
                        .then(function (response) {
                            if (!response.ok) throw new Error("Failed to reorder questions");
                            return response.text();
                        })
                        .then(function (html) {
                            const wrapper = document.createElement("div");
                            wrapper.innerHTML = html.trim();
                            const newList = wrapper.firstElementChild;

                            if (newList) {
                                list.replaceWith(newList);
                                initSectionSortable();
                                initQuestionSortable();
                                initAnswerSortable();
                                initPreparationUI(document);
                                initMarkdownEditors(document);
                            }
                        })
                        .catch(function (error) {
                            console.error("[preparation.js] reorderQuestions failed:", error);
                        });
                }
            });
        });
    }


    function initAnswerSortable() {
        if (typeof Sortable === "undefined" || isExamFinalized()) {
            return;
        }

        document.querySelectorAll('[id^="prep-answers-list-"]').forEach(function (list) {
            const questionId = list.dataset.questionId;
            if (!questionId || !URLS.reorderAnswersTemplate ) return;

            if (list._sortableInstance) {
                list._sortableInstance.destroy();
            }

            list._sortableInstance = Sortable.create(list, {
                handle: Selectors.dragHandle,
                draggable: ".sortable-answer-wrapper",
                animation: 150,
                onEnd: function () {
                    const orderedAnswers = [];

                    list.querySelectorAll(".sortable-answer-wrapper").forEach(function (card, index) {
                        orderedAnswers.push({
                            id: card.dataset.answerId,
                            position: index + 1
                        });
                    });

                    const url = URLS.reorderAnswersTemplate.replace("__QUESTION_ID__", questionId);

                    fetch(url, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": CSRF
                        },
                        body: JSON.stringify({ answers: orderedAnswers })
                    })
                        .then(function (response) {
                            if (!response.ok) throw new Error("Failed to reorder answers");
                            return response.text();
                        })
                        .then(function (html) {
                            const wrapper = document.createElement("div");
                            wrapper.innerHTML = html.trim();
                            const newBlock = wrapper.firstElementChild;

                            const target = document.getElementById(`answers-containers-${questionId}`);
                            if (newBlock && target) {
                                target.replaceWith(newBlock);
                                initSectionSortable();
                                initQuestionSortable();
                                initAnswerSortable();
                                initPreparationUI(document);
                                initMarkdownEditors(document);
                            }
                        })
                        .catch(function (error) {
                            console.error("[preparation.js] reorderAnswers failed:", error);
                        });
                }
            });
        });
    }

    // =============================
    // Markdown editors manager
    // =============================

    function collectMarkdownTextareas(root = document) {
        if (!root) return [];

        const textareas = [];

        if (root.matches && root.matches("textarea.markdown-editor")) {
            textareas.push(root);
        }

        if (root.querySelectorAll) {
            textareas.push(...root.querySelectorAll("textarea.markdown-editor"));
        }

        return textareas;
    }

    function syncTextarea(textarea) {
        const instance = markdownEditors.get(textarea);
        if (!instance) return;

        textarea.value = instance.editor.getMarkdown();
    }

    function syncMarkdownEditors(rootOrForm = document) {
        collectMarkdownTextareas(rootOrForm).forEach((textarea) => {
            syncTextarea(textarea);
        });
    }

    function destroyMarkdownEditors(root = document) {
        collectMarkdownTextareas(root).forEach((textarea) => {
            const instance = markdownEditors.get(textarea);
            if (!instance) return;

            syncTextarea(textarea);
            instance.editor.destroy();

            if (instance.container && instance.container.parentNode) {
                instance.container.remove();
            }

            textarea.style.display = "";
            markdownEditors.delete(textarea);
            delete textarea.dataset.markdownEditorId;
        });
    }

    function initMarkdownEditors(root = document) {
        if (typeof toastui === "undefined" || !toastui.Editor) {
            return;
        }

        collectMarkdownTextareas(root).forEach((textarea) => {
            if (markdownEditors.has(textarea)) {
                return;
            }

            const container = document.createElement("div");
            container.className = "toastui-editor-container mb-3";

            textarea.parentNode.insertBefore(container, textarea.nextSibling);
            textarea.style.display = "none";

            const editor = new toastui.Editor({
                el: container,
                initialEditType: "wysiwyg",
                previewStyle: "vertical",
                height: "300px",
                initialValue: textarea.value || "",
                usageStatistics: false
            });

            const instance = {
                id: `md-${++markdownEditorSeq}`,
                editor: editor,
                container: container
            };

            markdownEditors.set(textarea, instance);
            textarea.dataset.markdownEditorId = instance.id;

            editor.on("change", function () {
                textarea.value = editor.getMarkdown();
            });
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

    // =============================
    // Edit LaTeX file managaement
    // =============================

    function openEditLaTeXFileDialog(type) {
        ajaxGet(URLS.editLatexFile, {type: type}, {
            success: (data) => {
                document.getElementById('latex_source_text').value = JSON.parse(data)[1];
                document.getElementById('edit_latex_file_modal_title').innerText = "Edit " + type;
                document.getElementById('edit_latex_file_type').innerText = type;
                $('#edit_latex_file_modal').modal('show');
            },
            error: (error) => {
                console.log(error);
            }
        })

    }

    function saveEditedLaTeXFile() {
        const data = {
            source: document.getElementById('latex_source_text').value,
            type: document.getElementById('edit_latex_file_type').innerText
        };

        ajaxPost(URLS.saveLatexFile, data, {
            success: (data) => {
                $('#edit_latex_file_modal').modal('hide');
            },
            error: (error) => {
                console.log(error);
            }
        })
    }

    // =============================
    // LaTeX packages management
    // =============================

    let latexAvailablePackages = [];
    let currentUsedPackages = [];

    function uniq(arr) {
        return [...new Set(arr)];
    }

    function sortStrings(arr) {
        return [...arr].sort((a, b) => a.localeCompare(b));
    }

    function normalizeAvailablePackages(rawPackages) {
        return uniq(
            (rawPackages || [])
                .map(pkg => typeof pkg === "string" ? pkg : pkg.name)
                .filter(Boolean)
        );
    }

    function normalizeUsedPackages(rawPackages) {
        return uniq((rawPackages || []).filter(Boolean));
    }

    function renderUsedPackages() {
        const container = document.getElementById("used_latex_packages_list");
        container.innerHTML = "";

        if (!currentUsedPackages.length) {
            container.innerHTML = `<div class="latex-empty-state">No package selected.</div>`;
            return;
        }

        sortStrings(currentUsedPackages).forEach(pkg => {
            const chip = document.createElement("div");
            chip.className = "latex-chip";

            const label = document.createElement("span");
            label.textContent = pkg;

            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.className = "latex-chip-remove";
            removeBtn.innerHTML = "&times;";
            removeBtn.title = `Remove ${pkg}`;
            removeBtn.onclick = () => removeUsedPackage(pkg);

            chip.appendChild(label);
            chip.appendChild(removeBtn);
            container.appendChild(chip);
        });
    }

    function getFilteredAvailablePackages(searchText = "") {
        const usedSet = new Set(currentUsedPackages);
        const query = searchText.trim().toLowerCase();

        return sortStrings(
            latexAvailablePackages.filter(pkg => {
                if (usedSet.has(pkg)) return false;
                if (!query) return true;
                return pkg.toLowerCase().includes(query);
            })
        ).slice(0, 50);
    }

    function renderPackageSearchResults(searchText = "") {
        const container = document.getElementById("latex_package_search_results");
        const results = getFilteredAvailablePackages(searchText);

        if (!results.length) {
            container.style.display = "none";
            container.innerHTML = "";
            return;
        }

        container.innerHTML = "";

        results.forEach(pkg => {
            const item = document.createElement("div");
            item.className = "latex-search-item";
            item.textContent = pkg;
            item.onclick = () => {
                addUsedPackage(pkg);
                document.getElementById("latex_package_search").value = "";
                renderPackageSearchResults("");
            };
            container.appendChild(item);
        });

        container.style.display = "block";
    }

    function addUsedPackage(pkg) {
        if (!pkg || currentUsedPackages.includes(pkg)) return;
        currentUsedPackages.push(pkg);
        currentUsedPackages = uniq(currentUsedPackages);
        renderUsedPackages();
    }

    function removeUsedPackage(pkg) {
        currentUsedPackages = currentUsedPackages.filter(p => p !== pkg);
        renderUsedPackages();
        renderPackageSearchResults(document.getElementById("latex_package_search").value);
    }

    function bindLatexPackageSearch() {
        const input = document.getElementById("latex_package_search");
        const results = document.getElementById("latex_package_search_results");

        input.oninput = () => {
            renderPackageSearchResults(input.value);
        };

        input.onfocus = () => {
            renderPackageSearchResults(input.value);
        };

        document.addEventListener("click", function (event) {
            if (!input.contains(event.target) && !results.contains(event.target)) {
                results.style.display = "none";
            }
        });
    }

    function openEditLaTeXPackagesDialog(type) {
        ajaxGet(URLS.editLatexPackages, {type: type}, {
            success: (data) => {
                if (typeof data === "string") {
                  data = JSON.parse(data);
                }

                latexAvailablePackages = normalizeAvailablePackages(data.latex_available_packages);
                currentUsedPackages = normalizeUsedPackages(data.used_packages);

                bindLatexPackageSearch();
                renderUsedPackages();
                renderPackageSearchResults("");

                $('#edit_latex_packages_modal').modal('show');
            },
            error: (error) => {
                console.log(error);
            }
        });
    }

    function saveEditedLaTeXPackages() {
        const data = {
            new_used_packages: currentUsedPackages
        };

        ajaxPost(URLS.saveLatexPackages, data, {
            success: (data) => {
                $('#edit_latex_packages_modal').modal('hide');
            },
            error: (error) => {
                console.log(error);
            }
        });
    }

    $(document).on("hidden.bs.modal", "#generate_final_exam_files_dialog", function () {
        stopGenFinalPolling();
        currentGenFinalJobId = null;

        if (genFinalWasSuccessful) {
            window.location.reload();
        }
    });

    $(document).on("hidden.bs.modal", "#exam_preview_dialog", function () {
        stopPreviewPolling();
        currentPreviewJobId = null;
    });


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

        const elt = event.detail.elt;
        const form = elt && elt.closest ? elt.closest("form") : null;
        if (!form) return;

        collectMarkdownTextareas(form).forEach((textarea) => {
            const instance = markdownEditors.get(textarea);
            if (!instance) return;

            const value = instance.editor.getMarkdown();
            textarea.value = value;
            event.detail.parameters[textarea.name] = value;
        });
    });

    document.body.addEventListener("htmx:beforeRequest", function (event) {
        const elt = event.detail.elt;
        const form = elt && elt.closest ? elt.closest("form") : null;
        if (form) {
            syncMarkdownEditors(form);
        }
    });

    document.body.addEventListener("htmx:beforeSwap", function (event) {
        const target = event.detail.target;
        if (!target) return;

        destroyMarkdownEditors(target);
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
        initSectionSortable();
        initQuestionSortable();
        initAnswerSortable();
        initPreparationUI(event.target);
        initMarkdownEditors(event.target);
    });

    document.addEventListener("DOMContentLoaded", function () {
        initSectionSortable();
        initQuestionSortable();
        initAnswerSortable();
        ScoringFormulasModal.bindEvents();
        initPreparationUI(document);
        initMarkdownEditors(document);

        const confirmUnlockBtn = document.getElementById("confirmUnlockEditingBtn");
        if (confirmUnlockBtn) {
            confirmUnlockBtn.addEventListener("click", confirmUnlockEditing);
        }
    });

    window.previewExam = previewExam;
    window.openEditLaTeXFileDialog = openEditLaTeXFileDialog;
    window.saveEditedLaTeXFile = saveEditedLaTeXFile;
    window.openEditLaTeXPackagesDialog = openEditLaTeXPackagesDialog;
    window.saveEditedLaTeXPackages = saveEditedLaTeXPackages;
    window.generateFinalExamFiles = generateFinalExamFiles;
    window.openUnlockEditingModal = openUnlockEditingModal;
})();