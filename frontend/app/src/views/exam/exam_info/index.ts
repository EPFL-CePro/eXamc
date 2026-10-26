import { byId, requireData } from '@examc/helpers/dom.ts';

import { initAccordion } from './accordion.ts';
import { initCommonExams } from './common-exams.ts';
import { initCatalog, initExamInfo, initExamOptions } from './exam.ts';
import { initQuestions } from './questions.ts';
import { initScales } from './scales.ts';
import { initUsers } from './users.ts';

document.addEventListener('DOMContentLoaded', () => {
    // Not rendered when the user isn't allowed to view the page.
    const root = byId('exam-info');
    const csrfToken = requireData(root, 'csrfToken');
    const finalScaleBtns = root.querySelectorAll<HTMLButtonElement>("button[data-final-scale-one-url]");

    initAccordion(byId('exam-info-accordion'));

    initExamInfo(byId<HTMLFormElement>('exam-info-form'), requireData(root, 'updateInfoUrl'));
    initExamOptions(byId<HTMLFormElement>('exam-options-form'), requireData(root, 'updateOptionsUrl'));
    initCatalog({ button: byId<HTMLButtonElement>("btn-show-catalog"), url: requireData(root, 'catalogUrl')});

    initScales({ createScaleUrl: requireData(root, 'createScaleUrl'), finalScaleBtns, csrfToken });

    initQuestions({
        form: byId<HTMLFormElement>('questions-form'),
        url: requireData(root, 'updateQuestionsUrl'),
        csrfToken,
        examPk: requireData(root, 'examPk'),
    });

    // Only rendered for the overall (COMMON) exam.
    const commonForm = document.getElementById('common-exams-form');
    if (commonForm instanceof HTMLFormElement) initCommonExams(commonForm);

    initUsers({
        searchUrl: requireData(root, 'ldapSearchUrl'),
        updateUrl: requireData(root, 'updateUsersUrl'),
        csrfToken,
    });
});