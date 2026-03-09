/* static/js/preparation.js */

(function () {
  "use strict";

  const CFG = window.EXAM_PREP_CONFIG || {};
  const URLS = CFG.urls || {};
  const CSRF = CFG.csrfToken || null;

  function showLoading(show) {
    const $modal = $("#loadingModal");
    if (!$modal.length) return;
    if (show) $modal.modal("show");
    else $modal.modal("hide");
  }

  function ajaxGet(url, data, { beforeSend, complete, success, error } = {}) {
    return $.ajax({
      url,
      type: "GET",
      data: data || {},
      beforeSend: beforeSend || function () { showLoading(true); },
      complete: complete || function () { showLoading(false); },
      success,
      error: error || function (xhr) { console.log(xhr); },
    });
  }

  function preview_exam() {
    if (!URLS.previewPdf) {
      console.warn("[preparation.js] Missing previewPdf URL");
      return;
    }

    $("#exam_preview_error").css("display", "none");
    $("#exam_preview_pdf").css("display", "none");

    ajaxGet(URLS.previewPdf, {}, {
      success: function (data) {
        if (typeof data === "string" && data.endsWith(".log")) {
          $("#exam_preview_error_message").val(data);
          $("#exam_preview_error").css("display", "block");
          $("#exam_preview_dialog").modal("show");
        } else {
          $("#exam_preview_pdf").attr("src", data);
          $("#exam_preview_pdf").css("display", "block");
          $("#exam_preview_dialog").modal("show");
        }
        showLoading(false);
      },
      error: function (xhr) {
        console.log(xhr);
        showLoading(false);
      },
    });
  }

  function initSectionSortable() {
    const list = document.getElementById("prep-sections-list");
    console.log("initSectionSortable", {
      listExists: !!list,
      reorderUrl: URLS.reorderSections,
      sortableExists: typeof Sortable !== "undefined"
    });
    if (!list || !URLS.reorderSections || typeof Sortable === "undefined") return;

    if (list._sortableInstance) {
      list._sortableInstance.destroy();
    }

    list._sortableInstance = Sortable.create(list, {
      handle: ".drag-handle",
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
          body: JSON.stringify({ sections: orderedSections })
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

  document.addEventListener("click", function (event) {
    const handle = event.target.closest(".drag-handle");
    if (handle) {
      event.stopPropagation();
    }
  });

  // Optional: ensure all HTMX requests include CSRF
  document.body.addEventListener("htmx:configRequest", function (event) {
    if (CSRF) {
      event.detail.headers["X-CSRFToken"] = CSRF;
    }
  });

  // Optional: if you need to do something after swaps later
  document.body.addEventListener("htmx:afterSwap", function () {
      initSectionSortable();
  });

  document.addEventListener("DOMContentLoaded", function () {
    initSectionSortable();
  });

  window.preview_exam = preview_exam;
})();