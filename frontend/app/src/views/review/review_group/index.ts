/**
 * The review page of a pages group: the copies' pages on the left, the page with its markers in
 * the middle, the grading schemes on the right. Each part is a module; this one starts them.
 */
import '@examc/components/resize-handle';

import {config} from './config';
import * as comments from './comments';
import * as gradingSchemes from './grading-schemes';
import * as markers from './markers';
import * as navigation from './navigation';
import * as pagesList from './pages-list';
import * as shortcuts from './shortcuts';
import * as tools from './tools';
import * as history from './history';
import * as tabletMode from './tablet-mode';
import * as pageView from './viewer/page-view';
import * as zoomPan from './viewer/zoom-pan';

import "./main.scss";


// MathJax: inline and display math in the comments
window.MathJax = {
    tex: {
        inlineMath: [['$$', '$$'], ['\\(', '\\)']],
        displayMath: [['\\[', '\\]']],
    },
};

// Called from inline handlers in the templates
window.updatePagesGroupCheckBox = (...args) => void gradingSchemes.updatePagesGroupCheckBox(...args);
window.sendScheme = gradingSchemes.sendScheme;
window.createMarker4CorrBox = markers.highlightBox;
window.saveStudentReportNote = (textarea) => void gradingSchemes.saveStudentReportNote(textarea);

// The modules listening to new pages and areas first, then the page view (which creates the first area)
markers.init();
tools.init();
history.init();
tabletMode.init();
comments.init();
gradingSchemes.init();
navigation.init();
zoomPan.init();
pageView.init();
shortcuts.init();

$('.modal-dialog').draggable();

/** Once everything is laid out (the table and the drawing area need their final size): open the first page. */
function start(): void {
    pagesList.init(navigation.goToEntry);
    navigation.start(Number(config.currPage) || 0);
}

if (document.readyState === 'complete') start();
else window.addEventListener('load', start, {once: true});
