import './main.scss';

import { byId, requireData } from '@examc/helpers/dom.ts';
import { initAssociation, openManualAssociationDialog, runAutomaticAssociation } from './association.ts';
import { initMarking, runMarking } from './marking.ts';
import { initStudents, openEditStudentsListModal, saveStudentsListFile, uploadStudentsFile } from './students.ts';
import { addStudentsTableRow, adjustStudentsTable } from './students-table/index.ts';

document.addEventListener('DOMContentLoaded', () => {
    const root = byId('amc-marking');
    const csvForm = byId<HTMLFormElement>('students-list-csv-form');
    const csvInput = byId<HTMLInputElement>('students-list-csv');

    initMarking({
        mark: requireData(root, 'markUrl'),
        csrfToken: requireData(root, 'csrfToken'),
    });
    initStudents({
        updateFile: requireData(root, 'updateStudentsFileUrl'),
        editFile: requireData(root, 'editFileUrl'),
        saveFile: requireData(root, 'saveEditedFileUrl'),
        amcView: requireData(root, 'amcViewUrl'),
    });
    initAssociation({
        automatic: requireData(root, 'automaticAssociationUrl'),
        manualData: requireData(root, 'manualAssociationDataUrl'),
        setManual: requireData(root, 'setManualAssociationUrl'),
    });

    // Marking
    byId('btn-mark').addEventListener('click', () => void runMarking());

    // Students list
    byId('btn-set-students-file').addEventListener('click', () => csvInput.click());
    csvInput.addEventListener('change', () => {
        if (csvInput.files?.length !== 1) return;
        void uploadStudentsFile(csvForm).finally(() => {
            csvInput.value = ''; // allow selecting the same file again
        });
    });
    byId('btn-edit-students-list').addEventListener('click', () => void openEditStudentsListModal());
    byId('btn-add-students-list-row').addEventListener('click', addStudentsTableRow);
    byId('btn-save-students-list').addEventListener('click', () => void saveStudentsListFile());
    byId('edit-students-list-modal').addEventListener('shown.bs.modal', adjustStudentsTable);

    // Association
    byId('btn-automatic-association').addEventListener('click', () => void runAutomaticAssociation());
    byId('btn-manual-association').addEventListener('click', () => void openManualAssociationDialog());
});