(function () {
    'use strict';

    /**
     * Global configuration object injected from Django template.
     * @typedef {Object} ReviewGroupConfig
     * @property {number} examId
     * @property {number} pagesGroupId
     * @property {boolean} useGradingScheme
     * @property {number} userId
     * @property {number} currPage
     * @property {string} csrfToken
     * @property {Object} urls
     * @property {Array<Object>} copiesPagesList
     * @property {number} totalCopiesPages
     */

    /** @type {ReviewGroupConfig} */
    const cfg = window.REVIEW_GROUP_CONFIG || {};

    let {
        examId,
        pagesGroupId,
        useGradingScheme,
        userId,
        currPage,
        csrfToken,
        urls,
        copiesPagesList,
        totalCopiesPages
    } = cfg;

    // ---------------------------------------------------------------------------
    // Global state for the review UI
    // ---------------------------------------------------------------------------

    /** Last marker.js state for the current page (JSON object). */
    let markerState = null;

    /** Data URL of the rendered annotated image. */
    let markedImageDataUrl = null;

    /** ID of the currently selected row/cell in the copies/pages table. */
    let currentSourceElementId = null;

    /** Parts of the current source ID: [prefix, copyNo, pageNo, rowId]. */
    let currentSourceIdParts = [];

    /** When coming from a "copy" jump, track original id to restore highlighting. */
    let fromCopyOriginalId = null;

    /** List of all copy/page combinations in the group. */
    let groupCopiesPagesList = copiesPagesList || [];

    /** Currently selected grading scheme id (string). */
    let currentGradingSchemeId = null;

    /** Coordinates for corrector boxes, each item is {x, y, corner}. */
    let correctorBoxesData = [];

    /** Magnifier on/off state. */
    let magnifierActive = false;

    /** Function that destroys the current magnifier, if any. */
    let destroyMagnifierFn = null;

    // ---------------------------------------------------------------------------
    // Marker.js setup
    // ---------------------------------------------------------------------------

    const {MarkerArea, Renderer} = markerjs3;
    const mjs3App = document.querySelector("#mjsapp");
    const markerWrapper = document.querySelector("#marker-wrapper");

    /** @type {MarkerArea} */
    let markerArea = new MarkerArea();
    markerWrapper.appendChild(markerArea);

    /** @type {HTMLImageElement} */
    let sourceImage = new Image();

    /**
     * Name of currently selected marker editor (e.g. 'TextMarker', 'FreehandMarker'),
     * or null when pointer/select mode is active.
     * @type {string|null}
     */
    let selectedMarkerEditor = null;

    // ---------------------------------------------------------------------------
    // Initial wiring & global event listeners
    // ---------------------------------------------------------------------------

    // When the image changes, recompute MarkerArea layout and redraw boxes
    sourceImage.onload = () => {
        layoutSourceImageAndBoxes();
    };

    // Make Bootstrap modals draggable
    $('.modal-dialog').draggable();

    // MathJax config for inline and display math
    window.MathJax = {
        tex: {
            inlineMath: [['$$', '$$'], ['\\(', '\\)']],
            displayMath: [['\\[', '\\]']],
        }
    };

    // Debounced resize: recompute layout instead of reloading page
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            layoutSourceImageAndBoxes();
        }, 150);
    });

    /**
     * Show/hide the bottom marker toolbar (color picker, etc.).
     * @param {boolean} show
     */
    function showBottomBar(show) {
        document.getElementById('mjs-bottom-bar').classList.toggle('show', show);
    }

    /**
     * Attach image to markerArea, size it to fit, and redraw corrector boxes.
     */
    function layoutSourceImageAndBoxes() {
        markerArea.targetImage = sourceImage;

        if (!mjs3App.contains(markerArea)) {
            mjs3App.appendChild(markerArea);
        }

        const rect = mjs3App.getBoundingClientRect();
        const imgW = sourceImage.naturalWidth || 1;
        const imgH = sourceImage.naturalHeight || 1;
        const imageRatio = imgW / imgH;

        const targetWidth = rect.width - 20;
        const targetHeight = targetWidth / imageRatio;

        markerArea.targetWidth = targetWidth;
        markerArea.targetHeight = targetHeight;

        $("#corrector_boxes_svg").empty();
        if (Array.isArray(correctorBoxesData) && correctorBoxesData.length > 0) {
            drawCorrectorBoxes();
        }
    }

    // ---------------------------------------------------------------------------
    // Pagination
    // ---------------------------------------------------------------------------

    /**
     * Build and render pagination controls, then load the copy/page
     * corresponding to the selected page index.
     *
     * @param {number} pages - Total number of pages (groupCopiesPagesList.length).
     * @param {number} page  - Currently selected page (1-based index).
     */
    function createPagination(pages, page) {
        const totalPages = Number(pages) || 0;
        if (totalPages <= 0) return;

        // Clamp current page to valid range [1, totalPages]
        let currentPage = Number(page) || 1;
        if (currentPage < 1) currentPage = 1;
        if (currentPage > totalPages) currentPage = totalPages;

        const container = document.getElementById("pagination");
        if (!container) return;

        container.innerHTML = "";

        // How many page numbers to show around the current one
        const RANGE = 1;

        /**
         * Helper to create a page link.
         *
         * @param {string} label        - Text shown in the link.
         * @param {number|null} target  - Page number to navigate to, or null for a disabled item.
         * @param {Object} [options]
         * @param {string} [options.id] - Optional DOM id.
         * @param {boolean} [options.active] - Mark this page as active.
         */
        function addPageLink(label, target, options = {}) {
            const a = document.createElement("a");
            a.textContent = label;
            a.href = "javascript:void(0)";
            a.className = "list-group-item list-group-item-action";

            if (options.id) {
                a.id = options.id;
            }

            if (options.active) {
                a.classList.add("active");
            }

            if (typeof target === "number") {
                a.addEventListener("click", () => {
                    createPagination(totalPages, target);
                });
            }

            container.appendChild(a);
            return a;
        }

        // Previous
        if (currentPage > 1) {
            addPageLink("Previous", currentPage - 1, {id: "previous_page"});
        }

        // Main page numbers: 1, ..., [current-RANGE..current+RANGE], ..., last
        if (currentPage > 1) {
            // First page
            addPageLink("1", 1, {active: currentPage === 1});

            const start = Math.max(2, currentPage - RANGE);

            if (start > 2) {
                const jumpBack = Math.max(1, currentPage - (RANGE + 1));
                addPageLink("...", jumpBack);
            }

            const end = Math.min(totalPages - 1, currentPage + RANGE);
            for (let p = start; p <= end; p++) {
                addPageLink(String(p), p, {active: p === currentPage});
            }

            if (end < totalPages - 1) {
                const jumpForward = Math.min(totalPages, currentPage + (RANGE + 1));
                addPageLink("...", jumpForward);
            }

            if (totalPages > 1) {
                addPageLink(String(totalPages), totalPages, {
                    active: currentPage === totalPages
                });
            }
        } else {
            // currentPage === 1
            const end = Math.min(totalPages, 1 + RANGE + 1);

            for (let p = 1; p <= end; p++) {
                addPageLink(String(p), p, {active: p === currentPage});
            }

            if (end < totalPages) {
                const jumpForward = Math.min(totalPages, end + 1);
                addPageLink("...", jumpForward);
                addPageLink(String(totalPages), totalPages, {
                    active: currentPage === totalPages
                });
            }
        }

        // Next
        if (currentPage < totalPages) {
            addPageLink("Next", currentPage + 1, {id: "next_page"});
        }

        // Load the copy/page associated with the current index
        const entry = groupCopiesPagesList[currentPage - 1];
        if (!entry) return;

        const copyNo = entry.copy_no;
        const pageNo = entry.page_no;

        currPage = currentPage;

        if (setMarkerArea(copyNo, pageNo)) {
            // Hide HighlightMarker (used only internally for corrector boxes)
            const highlightMarkers = document.querySelectorAll('[data-type-name="HighlightMarker"]');
            highlightMarkers.forEach(el => {
                el.style.display = "none";
            });
            if(useGradingScheme) {
                setGradingSchemeBlockActive(true);
            }

        } else {
            // If page is locked/unavailable, skip to next (or wrap)
            const nextPage = currentPage < totalPages ? currentPage + 1 : 1;
            if (nextPage !== currentPage) {
                createPagination(totalPages, nextPage);
            }
        }
    }

    /**
     * Update the main source image and table highlighting from a backend path.
     *
     * @param {string} scanPath - File path from backend.
     * @param {boolean} fromCopy - True if navigation came from a "copy" jump.
     */
    function setSourceScan(scanPath, fromCopy) {
        const oldAlt = sourceImage.alt;

        if (fromCopy && oldAlt) {
            const lastIdParts = oldAlt.split('_');
            fromCopyOriginalId = `${lastIdParts[0]}_${lastIdParts[1]}_${lastIdParts[2]}`;
        }

        const parts = scanPath.split('/');
        const srcUrl = "/" + parts[1] + "/" + parts[3];

        sourceImage.src = srcUrl;
        sourceImage.alt = parts[2];

        currentSourceIdParts = parts[2].split('_');
        currentSourceElementId = `${currentSourceIdParts[0]}_${currentSourceIdParts[1]}_${currentSourceIdParts[2]}`;
        const currentEl = document.getElementById(currentSourceElementId);
        if (!fromCopy) {
            if (currentEl) {
                currentSourceIdParts.push(currentEl.cells[0].innerText);
                currentEl.style.backgroundColor = "yellow";
            }
        }

        if (oldAlt && !fromCopy) {
            let lastElementId;
            if (fromCopyOriginalId !== null) {
                lastElementId = fromCopyOriginalId;
                fromCopyOriginalId = null;
            } else {
                lastElementId = oldAlt;
            }

            const lastEl = document.getElementById(lastElementId);
            if (lastEl && lastEl !== currentEl) {
                lastEl.style.backgroundColor = "";
            }
        }
    }

    // ---------------------------------------------------------------------------
    // Marker color helpers
    // ---------------------------------------------------------------------------

    /**
     * Synchronize color picker with current marker editor (strokeColor or text color).
     * @param {Object} editor - marker.js marker editor.
     */
    function syncColorUIFromEditor(editor) {
        if (!editor) return;

        let color = null;

        if ('strokeColor' in editor && editor.strokeColor) {
            color = editor.strokeColor;
        }
        if (!color && editor.marker && 'color' in editor.marker && editor.marker.color) {
            color = editor.marker.color;
        }

        if (!color) return;

        document.getElementById('color-input').value = color;
    }

    // Apply color picker changes back to current marker editor
    document.getElementById('color-input').addEventListener('input', (ev) => {
        const editor = markerArea.currentMarkerEditor;
        if (!editor) return;

        const newColor = ev.target.value;

        if ('strokeColor' in editor) {
            editor.strokeColor = newColor;
        }

        if (editor.marker && 'color' in editor.marker) {
            editor.marker.color = newColor;
        }
    });

    /**
     * Update toolbar active button and bottom bar visibility based on selected editor.
     */
    function updateMarkerToolbarSelection() {
        const buttons = document.querySelectorAll('#mjs-toolbar-center .btn');
        buttons.forEach(btn => btn.classList.remove('active'));

        switch (selectedMarkerEditor) {
            case 'TextMarker':
                document.getElementById('btn-text-marker').classList.add('active');
                showBottomBar(true);
                break;
            case 'FreehandMarker':
                document.getElementById('btn-freehand-marker').classList.add('active');
                showBottomBar(true);
                break;
            default:
                document.getElementById('btn-pointer').classList.add('active');
                showBottomBar(false);
        }
    }

    /**
     * Attach event handlers for marker toolbar buttons and markerArea events.
     * Called each time a new MarkerArea instance is created.
     */
    function bindMarkerToolbarEvents() {
        // Text marker
        document.getElementById('btn-text-marker').addEventListener('click', function () {
            markerArea.createMarker("TextMarker");
            selectedMarkerEditor = "TextMarker";
            updateMarkerToolbarSelection();
        });

        // Freehand marker
        document.getElementById('btn-freehand-marker').addEventListener('click', function () {
            markerArea.createMarker("FreehandMarker");
            selectedMarkerEditor = "FreehandMarker";
            updateMarkerToolbarSelection();
        });

        // Pointer / selection
        document.getElementById('btn-pointer').addEventListener('click', function () {
            markerArea.switchToSelectMode();
            selectedMarkerEditor = null;
            updateMarkerToolbarSelection();
        });

        // Clear markers (except HighlightMarker)
        document.getElementById('btn-clear').addEventListener('click', function () {
            const currentState = markerArea.getState();
            currentState.markers = currentState.markers.filter(
                m => m.typeName === 'HighlightMarker'
            );
            markerArea.restoreState(currentState);
            layoutSourceImageAndBoxes();
            onMarkerChange();
        });

        // Undo / Redo
        document.getElementById('btn-undo').addEventListener('click', function () {
            if (markerArea.isUndoPossible) {
                markerArea.undo();
                onMarkerChange();
            }
        });

        document.getElementById('btn-redo').addEventListener('click', function () {
            if (markerArea.isRedoPossible) {
                markerArea.redo();
                onMarkerChange();
            }
        });

        // Color button triggers color input
        document.getElementById('btn-color').addEventListener('click', (e) => {
            e.stopPropagation();
            document.getElementById('color-input').click();
        });

        // Delete key → delete selected markers (except when typing in an input)
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Delete') {
                const tag = document.activeElement && document.activeElement.tagName;
                if (tag === 'INPUT' || tag === 'TEXTAREA') {
                    return;
                }
                markerArea.deleteSelectedMarkers();
                e.preventDefault();
            }
        });

        // Marker events
        markerArea.addEventListener('markerdeselect', (ev) => {
            if (selectedMarkerEditor === ev.detail.markerEditor.marker.typeName) {
                selectedMarkerEditor = null;
                showBottomBar(false);
            }
            onMarkerChange();
        });

        markerArea.addEventListener("markerdelete", () => {
            onMarkerChange();
            showBottomBar(false);
        });

        markerArea.addEventListener('markerselect', (e) => {
            syncColorUIFromEditor(e.detail.markerEditor);
            selectedMarkerEditor = e.detail.markerEditor.marker.typeName;
            showBottomBar(true);
        });

        markerArea.addEventListener('markercreate', (e) => {
            syncColorUIFromEditor(e.detail.markerEditor);
        });

        markerArea.addEventListener('markerchange', (e) => {
            syncColorUIFromEditor(e.detail.markerEditor);
        });
    }

    // ---------------------------------------------------------------------------
    // MarkerArea lifecycle
    // ---------------------------------------------------------------------------

    /**
     * Recreate MarkerArea for given copy/page and restore markers if available.
     *
     * @param {number|string} copyNo
     * @param {number|string} pageNo
     * @param {boolean} [fromCopy=false]
     * @returns {boolean} true if markers loaded (page unlocked), false if locked.
     */
    function setMarkerArea(copyNo, pageNo, fromCopy = false) {
        markerWrapper.removeChild(markerArea);
        markerArea = new MarkerArea();
        markerWrapper.appendChild(markerArea);
        bindMarkerToolbarEvents();
        updateMarkerToolbarSelection();

        const ok = fetchMarkersAndComments(examId, copyNo, pageNo, fromCopy);
        if (!ok) return false;

        // After backend response, currentSourceIdParts may have been updated
        copyNo = currentSourceIdParts[1];
        pageNo = currentSourceIdParts[2];

        if (markerState) {
            markerArea.restoreState(markerState);
        }

        return true;
    }

    /**
     * Called whenever markers change: rasterizes state and sends it to backend.
     */
    async function onMarkerChange() {
        const renderer = new Renderer();
        renderer.targetImage = markerArea.targetImage;
        renderer.naturalSize = true;
        renderer.imageType = 'image/jpeg';

        markedImageDataUrl = await renderer.rasterize(markerArea.getState());
        persistMarkers(markerArea, examId, pagesGroupId);
    }

    // ---------------------------------------------------------------------------
    // Copy/page dropdown
    // ---------------------------------------------------------------------------

    /**
     * Initialize the copy/page dropdown for current copy.
     *
     * @param {Array<Object>} pages
     * @param {number|string} currentPageNo
     */
    function initCopyPagesSelectpicker(pages, currentPageNo) {
        const selectContainer = document.getElementById('copy_page_select');
        selectContainer.innerHTML = "";

        const wrapper = document.createElement('div');
        wrapper.className = 'page-picker-wrapper';
        selectContainer.appendChild(wrapper);

        // Button
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-sm btn-dark w-100';
        button.textContent = `page ${currentPageNo}`;
        wrapper.appendChild(button);

        // Carousel dropdown
        const carousel = document.createElement('div');
        carousel.className = 'page-carousel';
        carousel.style.display = 'none';

        // const centerLine = document.createElement('div');
        // centerLine.className = 'page-carousel-center-line';

        const list = document.createElement('div');
        list.className = 'page-carousel-list';

        // carousel.appendChild(centerLine);
        carousel.appendChild(list);
        wrapper.appendChild(carousel);

        // Current index
        let currentIndex = pages.findIndex(p =>
            Number(p.page_no) === Number(currentPageNo)
        );
        if (currentIndex === -1) currentIndex = 0;

        // Build items
        pages.forEach((pageData, index) => {
            const item = document.createElement('div');
            item.className = 'page-carousel-item btn-dark';
            item.textContent = `page ${pageData.page_no}`;
            item.dataset.copyNo = pageData.copy_no;
            item.dataset.pageNo = pageData.page_no;

            item.addEventListener('click', () => {
                setActive(index);              // mark selected
                button.textContent = `page ${item.dataset.pageNo}`;
                changeCopyPage(examId, item.dataset.copyNo, item.dataset.pageNo);
                hideCarousel();
            });

            list.appendChild(item);
        });

        const items = Array.from(list.children);

        function setActive(index) {
            if (!items.length) return;
            if (index < 0 || index >= items.length) return;
            currentIndex = index;

            items.forEach((el, i) => {
                el.classList.toggle('page-active', i === currentIndex);
            });
        }

        function centerOnCurrent() {
            if (!items.length) return;
            const itemHeight = items[0].offsetHeight;
            const boxHeight = carousel.clientHeight;  // actual height (<= 50vh)
            if (!boxHeight) return;

            const itemTop = currentIndex * itemHeight;
            let targetScroll = itemTop - (boxHeight - itemHeight) / 2;

            // clamp so we don't scroll negative or beyond max
            const maxScroll = carousel.scrollHeight - boxHeight;
            if (targetScroll < 0) targetScroll = 0;
            if (targetScroll > maxScroll) targetScroll = maxScroll;

            carousel.scrollTop = targetScroll;
        }

        function showCarousel() {
            carousel.style.display = 'block';
            // Wait a tick so the browser lays out heights correctly
            requestAnimationFrame(() => {
                setActive(currentIndex);
                centerOnCurrent();          // current page centered on open
            });
        }

        function hideCarousel() {
            carousel.style.display = 'none';
        }

        button.addEventListener('click', () => {
            const hidden =
                carousel.style.display === 'none' || carousel.style.display === '';
            if (hidden) showCarousel(); else hideCarousel();
        });

        // Initial: just mark current, scrolling happens when first opened
        if (items.length) {
            setActive(currentIndex);
        }
    }

    function setGradingSchemeBlockActive(isActive) {
      const overlay = document.getElementById('grading-scheme-block-overlay');

      if (isActive) {
        overlay.style.display = 'none';   // show overlay, block interaction
      } else {
        overlay.style.display = 'flex';   // hide overlay, allow interaction
      }
    }


    /**
     * Request a new copy/page from backend and update MarkerArea accordingly.
     */
    function changeCopyPage(examIdParam, copyNo, pageNo) {
        $.ajax({
            url: urls.getCopyPage,
            type: "POST",
            data: {
                'csrfmiddlewaretoken': csrfToken,
                'copy_no': copyNo,
                'page_no': pageNo,
            },
            success: () => {
                setMarkerArea(copyNo, pageNo, true);
                //disable grading scheme if not in pages group for review
                const exists = copiesPagesList.some(item =>
                  item.copy_no === copyNo && item.page_no === pageNo
                );
                if(useGradingScheme) {
                    setGradingSchemeBlockActive(exists);
                }
            },
        });
    }

    /**
     * Fetch markers & comments for given copy/page, handle locking and grading panel.
     *
     * @returns {boolean} true on success (unlocked), false if page is locked.
     */
    function fetchMarkersAndComments(examIdParam, copyNo, pageNo, fromCopy = false) {
        let result = false;

        $.ajax({
            url: urls.reviewStudentPageLocked,
            async: false,
            type: "POST",
            data: {
                'csrfmiddlewaretoken': csrfToken,
                'pages_group_id': pagesGroupId,
                'copy_no': copyNo,
            },
            success: (data) => {
                if (data === '') {
                    const tdEl = document.getElementById(`copy_${copyNo}_${Number(pageNo)}_id`);
                    if (tdEl) tdEl.style.display = 'None';

                    $.ajax({
                        url: urls.getMarkersAndComments,
                        async: false,
                        type: "POST",
                        data: {
                            'csrfmiddlewaretoken': csrfToken,
                            'copy_no': copyNo,
                            'page_no': String(pageNo),
                            'group_id': pagesGroupId
                        },
                        success: (raw) => {
                            if (raw !== "None") {
                                const dataFull = JSON.parse(raw);

                                setSourceScan(dataFull.copyPageUrl, fromCopy);

                                markerState = JSON.parse(dataFull.markers);
                                const comments = dataFull.comments;
                                correctorBoxesData = JSON.parse(dataFull.corrector_boxes);
                                initComments(comments);
                                const pages = JSON.parse(dataFull.copy_pages);
                                initCopyPagesSelectpicker(pages, pageNo);

                                // Refresh grading scheme panel
                                const active =
                                    document.querySelector('a[id^="review-scheme-link-"].active') ||
                                    document.querySelector('a[id^="review-scheme-link-"]');
                                if (active) {
                                    setTimeout(() => sendScheme(active), 0);
                                }
                            }
                            result = true;
                        },
                        error: console.log
                    });
                } else {
                    const tdEl = document.getElementById(`copy_${copyNo}_${Number(pageNo)}_id`);
                    if (tdEl) tdEl.style.display = 'block';
                    result = false;
                }
            },
            error: console.log
        });
        return result;
    }

    // ---------------------------------------------------------------------------
    // Corrector boxes overlay (SVG)
    // ---------------------------------------------------------------------------

    /**
     * Draw corrector boxes as SVG polygons overlayed on the image.
     * Uses original coordinates (correctorBoxesData) scaled to current zoom.
     */
    function drawCorrectorBoxes() {
        const svgns = 'http://www.w3.org/2000/svg';

        const baseWidth = sourceImage.naturalWidth || 1;
        let imgScale = markerArea.targetWidth / baseWidth;
        imgScale = imgScale * markerArea.zoomLevel;

        const corrBoxDiv = document.getElementById('corr_box_div');
        if (!corrBoxDiv) return;

        corrBoxDiv.style.position = 'absolute';
        corrBoxDiv.style.zIndex = '988';
        corrBoxDiv.style.width = '75%';

        const xs = correctorBoxesData.map(p => p.x);
        const ys = correctorBoxesData.map(p => p.y);

        const minX = Math.min(...xs);
        const maxX = Math.max(...xs);
        const minY = Math.min(...ys);
        const maxY = Math.max(...ys);

        const xPos = minX * imgScale;
        const yPos = minY * imgScale;
        const margin = 10;

        corrBoxDiv.id = 'corr_box_div';
        corrBoxDiv.style.height = `${(maxY - minY) * imgScale}px`;
        corrBoxDiv.style.left = `${xPos}px`;
        corrBoxDiv.style.top = `${yPos}px`;
        corrBoxDiv.style.margin = `${margin}px`;

        let boxesSvg = corrBoxDiv.querySelector('#corrector_boxes_svg');
        if (!boxesSvg) {
            boxesSvg = document.createElementNS(svgns, 'svg');
            boxesSvg.id = 'corrector_boxes_svg';
            boxesSvg.setAttribute('style', 'width:100%;height:100%;');
            corrBoxDiv.appendChild(boxesSvg);
        }

        let polygon = null;
        let boxLeft = 0;
        let boxTop = 0;
        let boxWidth = 0;
        let boxHeight = 0;

        for (let pos of correctorBoxesData) {
            if (pos.corner === 1) {
                boxLeft = pos.x * imgScale;
                boxTop = pos.y * imgScale;
                polygon = document.createElementNS(svgns, 'polygon');
            }

            if (polygon) {
                const point = boxesSvg.createSVGPoint();
                point.x = pos.x * imgScale - xPos;
                point.y = pos.y * imgScale - yPos;
                polygon.points.appendItem(point);
            }

            if (pos.corner === 2) {
                boxWidth = (pos.x * imgScale) - boxLeft;
            }

            if (pos.corner === 4 && polygon) {
                boxHeight = (pos.y * imgScale) - boxTop;
                boxesSvg.appendChild(polygon);
                polygon.setAttribute('fill', 'transparent');
                polygon.setAttribute('stroke', 'purple');
                polygon.setAttribute('stroke-width', '3');
                polygon.setAttribute('opacity', '0.7');
                polygon.setAttribute('data-bounds', `${boxLeft},${boxTop},${boxWidth},${boxHeight}`);
                if (!useGradingScheme) {
                    polygon.setAttribute(
                        'onclick',
                        `createMarker4CorrBox(${boxLeft},${boxTop},${boxWidth},${boxHeight});`
                    );
                }
                polygon = null;
            }
        }

        const corrHeight = maxY * imgScale - yPos + 1;
        corrBoxDiv.style.height = `${corrHeight}px`;
    }

    /**
     * Highlight a corrector box using a single HighlightMarker in MarkerArea.
     * If left = -1, all highlight markers are removed.
     */
    function createMarker4CorrBox(left, top, width, height) {
        const state = markerArea.getState();
        const markers = state.markers ? [...state.markers] : [];

        let shouldAddMarker = true;

        // Remove existing HighlightMarker and decide if we add a new one
        for (let i = markers.length - 1; i >= 0; i--) {
            const m = markers[i];
            if (m.typeName === 'HighlightMarker') {
                shouldAddMarker = false;

                if (
                    left !== -1 &&
                    (m.left !== left ||
                        m.top !== top ||
                        m.width !== width ||
                        m.height !== height)
                ) {
                    shouldAddMarker = true;
                }
                markers.splice(i, 1);
            }
        }

        if (shouldAddMarker && left !== -1) {
            const newMarkerState = {
                typeName: 'HighlightMarker',
                left,
                top,
                width,
                height,
                fillColor: 'black',
                opacity: 1,
                rotationAngle: 0,
            };
            markers.push(newMarkerState);
        }

        const newState = {...state, markers};
        markerArea.restoreState(newState);
        onMarkerChange();
    }

    // ---------------------------------------------------------------------------
    // Copy/pages table
    // ---------------------------------------------------------------------------

    /**
     * Initialize / refresh the DataTable and row click events for the copies/pages table.
     *
     * @param {boolean} refresh - If true, only rebind click handler; if false, also (re)init DataTable.
     */
    function initCopyPagesTableOnClickRowEvent(refresh) {
        $("#table-copies-pages").off().on('click', 'tr', function () {
            createPagination(copiesPagesList.length, parseFloat(this.cells[1].innerText));
        });

        if (!refresh) {
            $("#table-copies-pages").DataTable({
                scrollY: '80vh',
                dom: 'rtip',
                lengthChange: false,
                paging: false,
            });
        }
    }

    /**
     * Send markers + rasterized image to backend and keep table highlight in sync.
     */
    function persistMarkers(markerAreaParam, examIdParam, groupId) {
        const copyNo = currentSourceIdParts[1];
        const pageNo = currentSourceIdParts[2];
        const rowId = currentSourceIdParts[3];

        saveMarkers(
            examIdParam,
            groupId,
            copyNo,
            pageNo,
            JSON.stringify(markerAreaParam.getState()),
            markedImageDataUrl,
            sourceImage.getAttribute("src"),
            rowId
        );

        initCopyPagesTableOnClickRowEvent(true);
        const currentEl = document.getElementById(currentSourceElementId);
        if (currentEl) {
            currentEl.style.backgroundColor = "yellow";
        }
    }

    /**
     * AJAX: save markers and rasterized image to backend.
     */
    function saveMarkers(examIdParam, groupId, copyNo, pageNo, markersJson, markedImgDataUrl, filename, rowId) {
        $.ajax({
            url: urls.saveMarkers,
            type: "POST",
            data: {
                'csrfmiddlewaretoken': csrfToken,
                'reviewGroup_pk': groupId,
                'curr_row': rowId,
                'copy_no': copyNo,
                'page_no': "" + pageNo,
                'markers': markersJson,
                'marked_img_dataUrl': markedImgDataUrl,
                'filename': filename
            },
            success: (marked) => {
                const markedInfoEl = document.getElementById(currentSourceElementId + "_marked");
                if (!markedInfoEl) return;

                markedInfoEl.innerHTML = "";
                if (marked === 'True') {
                    markedInfoEl.innerHTML =
                        '<i class="fa-solid fa-circle-check fa-lg" style="padding-left:25px;">';
                }
            },
        });
    }

    // ---------------------------------------------------------------------------
    // Comments (jquery-comments)
    // ---------------------------------------------------------------------------

    /**
     * Save or update a comment via backend.
     * Used by jquery-comments postComment/putComment.
     */
    function saveComment(data) {
        const copyNo = currentSourceIdParts[1];

        // Convert pings to human readable format (@id → @Full Name)
        $(Object.keys(data.pings)).each((index, userId) => {
            const fullname = data.pings[userId];
            const pingText = '@' + fullname;
            data.content = data.content.replace(new RegExp('@' + userId, 'g'), pingText);
        });

        $.ajax({
            url: urls.saveComment,
            type: "POST",
            async: false,
            data: {
                'csrfmiddlewaretoken': csrfToken,
                'comment': JSON.stringify(data),
                'group_id': pagesGroupId,
                'copy_no': copyNo
            },
        });

        return data;
    }

    /**
     * Delete a comment via backend.
     * Used by jquery-comments deleteComment.
     */
    function deleteComment(data) {
        const copyNo = currentSourceIdParts[1];

        $.ajax({
            url: urls.saveComment,
            type: "POST",
            async: false,
            data: {
                'csrfmiddlewaretoken': csrfToken,
                'comment_id': data.id,
                'group_id': pagesGroupId,
                'copy_no': copyNo,
                'delete': true
            },
        });

        return data;
    }

    /**
     * Initialize jquery-comments with comment list for the current copy/page.
     */
    function initComments(commentsArray) {
        $('#comments-container').comments({
            profilePictureURL: 'fa-solid fa-circle-user fa-2xs',
            currentUserId: userId,
            roundProfilePictures: true,
            textareaRows: 1,
            enableAttachments: false,
            enableHashtags: false,
            enableUpvoting: false,
            enableEditing: true,
            enableDeleting: true,
            scrollContainer: $(window),
            getComments: function (success, error) {
                setTimeout(() => success(commentsArray), 500);
            },
            postComment: function (data, success, error) {
                setTimeout(() => success(saveComment(data)), 500);
            },
            putComment: function (data, success, error) {
                setTimeout(() => success(saveComment(data)), 500);
            },
            deleteComment: function (data, success, error) {
                setTimeout(() => success(deleteComment(data)), 500);
            },
        });
    }

    // ---------------------------------------------------------------------------
    // Initial bootstrap (window load)
    // ---------------------------------------------------------------------------

    $(window).on("load", function () {
        initCopyPagesTableOnClickRowEvent(false);

        if (currPage > 0) {
            createPagination(copiesPagesList.length, currPage);
        } else {
            const firstId = `copy_${copiesPagesList[0].copy_no}_${copiesPagesList[0].page_no}`;
            document.getElementById(firstId).click();
            setTimeout(() => {
                document.getElementById(firstId).click();
            }, 350);
        }

        SidebarCollapse();

        // Keyboard arrows → previous/next page
        $('#reviewGroup_div').on('keydown', function (event) {
            // If a TextMarker is selected (editing/selection state), don't paginate on arrows.
            if (selectedMarkerEditor === 'TextMarker') {
                return;
            }
            switch (event.key) {
                case "ArrowLeft":
                case "ArrowUp": {
                    const previousBtn = document.getElementById('previous_page');
                    if (previousBtn) previousBtn.click();
                    break;
                }
                case "ArrowRight":
                case "ArrowDown": {
                    const nextBtn = document.getElementById('next_page');
                    if (nextBtn) nextBtn.click();
                    break;
                }
            }
        }).focus();
    });

    // Expand/collapse left group list panel
    document.getElementById("expandCollapseGroupListBt").addEventListener("click", function () {
        const expandIcon = $("#expand-group-list-icon");
        const collapseIcon = $("#collapse-group-list-icon");
        if (collapseIcon.hasClass('fa-angle-double-left')) {
            collapseIcon.removeClass('fa-angle-double-left');
            expandIcon.addClass("fa-solid fa-table-list");
            expandIcon.show();
            collapseIcon.hide();
        } else {
            expandIcon.removeClass('fa-solid fa-table-list');
            collapseIcon.addClass("fa-angle-double-left");
            collapseIcon.show();
            expandIcon.hide();
        }
    });

    // ---------------------------------------------------------------------------
    // Magnifier (zoom glass)
    // ---------------------------------------------------------------------------

    /**
     * Create a magnifier glass over given element.
     *
     * @param {string} elementID - Id of the element to attach magnifier to.
     * @param {number} zoom      - Zoom factor.
     * @returns {Function} destroyMagnifier - Cleanup function.
     */
    function createDivMagnifier(elementID, zoom) {
        const elem = document.getElementById(elementID);

        const glass = document.createElement("div");
        glass.classList.add("magnifier-glass");
        elem.parentElement.insertBefore(glass, elem);

        glass.style.backgroundImage = `url('${sourceImage.src}')`;
        glass.style.backgroundRepeat = "no-repeat";
        glass.style.backgroundSize =
            (markerArea.targetWidth * zoom) + "px " + (markerArea.targetHeight * zoom) + "px";

        const borderWidth = 3;
        const halfWidth = glass.offsetWidth / 2;
        const halfHeight = glass.offsetHeight / 2;

        function getCursorPos(e) {
            e = e || window.event;
            const rect = elem.getBoundingClientRect();
            const x = e.pageX - rect.left - window.pageXOffset;
            const y = e.pageY - rect.top - window.pageYOffset;
            return {x, y};
        }

        function moveMagnifier(e) {
            e.preventDefault();
            const pos = getCursorPos(e);
            let x = pos.x;
            let y = pos.y;

            if (x > elem.offsetWidth - halfWidth / zoom) x = elem.offsetWidth - halfWidth / zoom;
            if (x < halfWidth / zoom) x = halfWidth / zoom;
            if (y > elem.offsetHeight - halfHeight / zoom) y = elem.offsetHeight - halfHeight / zoom;
            if (y < halfHeight / zoom) y = halfHeight / zoom;

            glass.style.left = (x - halfWidth) + "px";
            glass.style.top = (y - halfHeight) + "px";

            glass.style.backgroundPosition =
                "-" + ((x * zoom) - halfWidth + borderWidth) + "px " +
                "-" + ((y * zoom) - halfHeight + borderWidth) + "px";
        }

        elem.addEventListener("mousemove", moveMagnifier);
        elem.addEventListener("touchmove", moveMagnifier);
        elem.addEventListener("mouseenter", (e) => moveMagnifier(e));

        return function destroyMagnifier() {
            elem.removeEventListener("mousemove", moveMagnifier);
            elem.removeEventListener("touchmove", moveMagnifier);
            glass.remove();
        };
    }

    // Toggle magnifier button
    document.getElementById("btn-magnify").addEventListener("click", function () {
        if (!magnifierActive) {
            destroyMagnifierFn = createDivMagnifier("marker-wrapper", 2);
            magnifierActive = true;
            document.getElementById("magnify-help").classList.remove("d-none");
        } else {
            if (destroyMagnifierFn) destroyMagnifierFn();
            magnifierActive = false;
            document.getElementById("magnify-help").classList.add("d-none");
        }
    });

    // Disable magnifier when clicking outside
    document.addEventListener("click", function (e) {
        if (!magnifierActive) return;

        const zoomElem = document.getElementById("marker-wrapper");
        const magnifyBtn = document.getElementById("btn-magnify");
        const clicked = e.target;

        if (zoomElem.contains(clicked) || magnifyBtn.contains(clicked)) {
            return;
        }

        if (destroyMagnifierFn) destroyMagnifierFn();
        magnifierActive = false;
        document.getElementById("magnify-help").classList.add("d-none");
    });

    // ---------------------------------------------------------------------------
    // Grading schemes (pills + checkboxes + HTMX panel)
    // ---------------------------------------------------------------------------

    /**
     * Disable all grading schemes except the active one, with tooltip explanation.
     */
    function disableOtherSchemesExcept(activeId) {
        document.querySelectorAll('#review-scheme-pills .nav-link').forEach(a => {
            const id = a.id.replace('review-scheme-link-', '');
            if (id !== String(activeId)) {
                a.classList.add('disabled');
                a.setAttribute('aria-disabled', 'true');
                a.setAttribute('tabindex', '-1');

                const usedLink = document.getElementById('review-scheme-link-' + activeId);
                const usedName = usedLink ? usedLink.textContent.trim() : `#${activeId}`;
                const msg = "This scheme can't be used because " + usedName + " is already used !";

                a.parentNode.setAttribute('data-toggle', 'tooltip');
                a.parentNode.setAttribute('data-placement', 'top');
                a.parentNode.setAttribute('title', msg);

                let tip = bootstrap.Tooltip.getInstance(a);
                if (tip) {
                    tip.setContent({'.tooltip-inner': msg});
                } else {
                    tip = new bootstrap.Tooltip(a);
                }
            }
        });
    }

    /**
     * Re-enable all grading schemes and remove tooltips.
     */
    function enableAllSchemes() {
        document.querySelectorAll('#review-scheme-pills .nav-link').forEach(a => {
            a.classList.remove('disabled');
            a.removeAttribute('aria-disabled');
            a.removeAttribute('tabindex');

            const tip = bootstrap.Tooltip.getInstance(a);
            if (tip) tip.dispose();
            a.parentNode.removeAttribute('data-toggle');
            a.parentNode.removeAttribute('data-placement');
            a.parentNode.removeAttribute('title');
        });
    }

    /**
     * Called when a grading scheme checkbox or its adjustment changes.
     * Updates backend, points display, highlight, and corrector box highlight.
     *
     * NOTE: name kept so Django's inline `onchange="updatePagesGroupCheckBox(...)"` still works.
     */
    function updatePagesGroupCheckBox(itemId, checked, isAdjustment, zero) {
        let adjustValue = isAdjustment;

        if (isAdjustment) {
            const checkboxId = itemId.replace('adj', 'check');
            checked = document.getElementById(checkboxId).checked;
        } else {
            const adjustId = itemId.replace('check', 'adj');
            const adjustEl = document.getElementById(adjustId);
            if (adjustEl) {
                adjustValue = adjustEl.value;
            }
        }

        $.ajax({
            url: urls.updatePagesGroupCheckBox,
            type: "POST",
            data: {
                'csrfmiddlewaretoken': csrfToken,
                'item_id': itemId,
                'copy_nr': currentSourceIdParts[1],
                'checked': checked,
                'adjustment': adjustValue,
                'pages_group_id': pagesGroupId,
                'grading_scheme_id': currentGradingSchemeId,
                'zero': zero
            },
            success: (response) => {
                if (response === '') return;

                const respData = JSON.parse(response);
                const corrBoxIndex = respData[0];
                const points = respData[1];
                const maxPointsRaw = respData[2];

                if (points !== '') {
                    const maxPoints = Number(maxPointsRaw);
                    const pointsContent =
                        Number(points).toFixed(2) + " / " + maxPoints.toFixed(2);
                    const pointsEl =
                        document.getElementById('gsc-points-' + currentGradingSchemeId);
                    if (pointsEl) pointsEl.textContent = pointsContent;

                    if (Number(points) > 0) {
                        disableOtherSchemesExcept(currentGradingSchemeId);
                    } else {
                        enableAllSchemes();
                    }
                }

                if (corrBoxIndex === -1) {
                    createMarker4CorrBox(-1, -1, -1, -1);
                } else {
                    const corrBoxesPolygons =
                        document.querySelectorAll('#corrector_boxes_svg polygon');
                    const polygonEl =
                        corrBoxesPolygons[parseInt(corrBoxIndex, 10)];
                    if (polygonEl) {
                        const pos = polygonEl
                            .getAttribute('data-bounds')
                            .split(',')
                            .map(Number);
                        createMarker4CorrBox(pos[0], pos[1], pos[2], pos[3]);
                    }
                }

                reloadGradingSchemeCheckboxPanel(currentGradingSchemeId);
            }
        });
    }

    /**
     * Reload the grading scheme checkbox panel via HTMX.
     */
    function reloadGradingSchemeCheckboxPanel(gradingSchemeId) {
        const el = document.getElementById('chk-panel-' + gradingSchemeId);
        if (!el) return;
        const url = el.getAttribute('hx-get');
        htmx.ajax('GET', url, {target: el, swap: 'innerHTML'});
    }

    /**
     * Handle click on grading scheme pill:
     *  - updates HTMX URL with current copy number,
     *  - loads scheme panel,
     *  - applies active/disabled state based on server headers.
     *
     * NOTE: name kept so Django's inline `onclick="sendScheme(...)"` still works.
     */
    function sendScheme(el, evt) {
        if (evt) {
            evt.preventDefault();
            evt.stopPropagation();
        }

        el.classList.add('active');
        el.setAttribute('aria-selected', 'true');

        let currentUrl = el.getAttribute('data-hx-get') || '';
        const copyNo = currentSourceIdParts[1];
        if (copyNo == null) return false;

        const updatedUrl = currentUrl.replace(/\/[^/?#]+(?=[?#]|$)/, '/' + encodeURIComponent(copyNo));
        el.setAttribute('data-hx-get', updatedUrl);

        const onAfterSwap = (e) => {
            if (!e.detail || !e.detail.target || e.detail.target.id !== 'review-scheme-panel') return;

            const usedId = e.detail.xhr &&
                e.detail.xhr.getResponseHeader('X-Used-Grading-Scheme-Id');
            const activeId = usedId || el.id.replace('review-scheme-link-', '');
            currentGradingSchemeId = activeId;

            document.querySelectorAll('#review-scheme-pills .nav-link').forEach(a => {
                a.classList.remove('active');
                a.setAttribute('aria-selected', 'false');
            });

            const points = e.detail.xhr.getResponseHeader('X-Points');
            if (points !== '' && points > 0) {
                disableOtherSchemesExcept(usedId);
            } else {
                enableAllSchemes();
            }

            const toActivate = document.getElementById('review-scheme-link-' + activeId);
            if (toActivate) {
                toActivate.classList.add('active');
                toActivate.setAttribute('aria-selected', 'true');
            }

            const examIdAttr = el.getAttribute('data-exam-id');
            const checkPanel = document.getElementById('chk-panel-' + activeId);
            if (checkPanel && examIdAttr) {
                const chkUrl =
                    `/review_grading_scheme_checkboxes/${examIdAttr}/${activeId}/${encodeURIComponent(copyNo)}`;
                checkPanel.setAttribute('hx-get', chkUrl);
                htmx.ajax('GET', chkUrl, {target: checkPanel, swap: 'innerHTML', source: checkPanel});
            }

            document.body.removeEventListener('htmx:afterSwap', onAfterSwap);
        };
        document.body.addEventListener('htmx:afterSwap', onAfterSwap);

        htmx.ajax('GET', updatedUrl, {
            target: '#review-scheme-panel',
            swap: 'innerHTML',
            source: el
        });

        return false;
    }

    // ---------------------------------------------------------------------------
    // Splitter for grading scheme panel (vertical)
    // ---------------------------------------------------------------------------

    (function () {
        const MIN_TOP = 80;   // px
        const MIN_BOT = 120;  // px

        /**
         * Initialize vertical splitters inside root (or document by default).
         */
        function initSplitters(root = document) {
            const splits = root.querySelectorAll('.review-grading-scheme-split-vert');
            splits.forEach(split => {
                const handle = split.querySelector('.divider');
                if (!handle) return;
                if (handle.__splitBound) return;
                handle.__splitBound = true;

                let startY, startTop, maxTop;

                const getY = (e) => ('touches' in e ? e.touches[0].clientY : e.clientY);
                const px = (n) => `${n}px`;

                function onDown(e) {
                    const rect = split.getBoundingClientRect();
                    startY = getY(e);

                    const cs = getComputedStyle(split);
                    const varTop = parseFloat(cs.getPropertyValue('--top')) || NaN;
                    const row0 = parseFloat(cs.gridTemplateRows.split(' ')[0]);
                    startTop = isNaN(varTop) ? row0 : varTop;

                    maxTop = rect.height - MIN_BOT - handle.offsetHeight;

                    document.body.classList.add('dragging');

                    window.addEventListener('mousemove', onMove, {passive: false});
                    window.addEventListener('touchmove', onMove, {passive: false});
                    window.addEventListener('mouseup', onUp, {once: true});
                    window.addEventListener('touchend', onUp, {once: true});

                    e.preventDefault();
                }

                function onMove(e) {
                    const dy = getY(e) - startY;
                    let newTop = Math.min(Math.max(startTop + dy, MIN_TOP), maxTop);
                    split.style.setProperty('--top', px(newTop));
                    e.preventDefault();
                }

                function onUp() {
                    document.body.classList.remove('dragging');
                    window.removeEventListener('mousemove', onMove);
                    window.removeEventListener('touchmove', onMove);
                }

                handle.addEventListener('mousedown', onDown);
                handle.addEventListener('touchstart', onDown, {passive: false});
            });
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => initSplitters());
        } else {
            initSplitters();
        }

        // Re-init splitters when grading scheme panel is swapped by HTMX
        document.body.addEventListener('htmx:afterSwap', (evt) => {
            if (evt.target && evt.target.id === 'review-scheme-panel') {
                initSplitters(evt.target);
            }
        });
    })();

    // ---------------------------------------------------------------------------
    // Expose functions used from inline HTML
    // ---------------------------------------------------------------------------

    window.updatePagesGroupCheckBox = updatePagesGroupCheckBox;
    window.sendScheme = sendScheme;
    window.createMarker4CorrBox = createMarker4CorrBox;

})();
