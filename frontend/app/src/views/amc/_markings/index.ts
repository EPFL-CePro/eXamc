import { byId, requireData } from '@examc/helpers/dom.ts';
import { initAssociation, openManualAssociationDialog, runAutomaticAssociation } from './association.ts';
import { runMarking } from './marking.ts';
import { initStudents, openEditStudentsListModal, uploadStudentsFile } from './students.ts';
import { initTableMarkingDetails } from './table-marking-details.ts';

document.addEventListener('DOMContentLoaded', () => {
    const root = byId('amc-marking');
    const csvForm = byId<HTMLFormElement>('students-list-csv-form');
    const csvInput = byId<HTMLInputElement>('students-list-csv');
    const markingDetailsTable = byId<HTMLTableElement>('table-marking-details');

    const csrfToken = requireData(root, 'csrfToken');

    initTableMarkingDetails({ tableElement: markingDetailsTable});

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
    byId('btn-mark').addEventListener('click', () => void runMarking({ 
        mark: requireData(root, 'markUrl'), csrfToken 
    }));

    // Students list (the edit dialog wires its own buttons)
    byId('btn-set-students-file').addEventListener('click', () => csvInput.click());
    csvInput.addEventListener('change', () => {
        if (csvInput.files?.length !== 1) return;
        void uploadStudentsFile(csvForm).finally(() => {
            csvInput.value = ''; // allow selecting the same file again
        });
    });
    byId('btn-edit-students-list').addEventListener('click', () => void openEditStudentsListModal());

    // Association
    byId('btn-automatic-association').addEventListener('click', () => void runAutomaticAssociation());
    byId('btn-manual-association').addEventListener('click', () => void openManualAssociationDialog());
});