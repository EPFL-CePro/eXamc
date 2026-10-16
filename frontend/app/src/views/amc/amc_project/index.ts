import { byId, requireData } from '@examc/helpers/dom.ts';
import { type DocumentsUrls, runLayoutDetection, updateDocuments } from './documents.ts';
import { type FolderFiles, type FolderNode, openSourceFiles, type SourceFilesUrls } from './project.ts';

document.addEventListener('DOMContentLoaded', () => {
    const root = byId('amc-project');
    const csrfToken = requireData(root, 'csrfToken');

    // Source files
    const sourceFilesUrls: SourceFilesUrls = {
        editFile: requireData(root, 'editFileUrl'),
        saveFile: requireData(root, 'saveFileUrl'),
        csrfToken,
    };
    const projectDir = JSON.parse(byId('amc-project-dir').textContent ?? 'null') as FolderNode | null;
    const folderFiles = (JSON.parse(byId('amc-project-dir-files').textContent ?? 'null') as FolderFiles[] | null) ?? [];

    byId('btn-edit-source-files').addEventListener('click', () => openSourceFiles(sourceFilesUrls, projectDir, folderFiles));

    // Documents and layout
    const documentsUrls: DocumentsUrls = {
        updateDocuments: requireData(root, 'updateDocumentsUrl'),
        layoutDetection: requireData(root, 'layoutDetectionUrl'),
        logFile: requireData(root, 'logFileUrl'),
        csrfToken,
    };

    const numberOfCopiesEl = byId<HTMLInputElement>('number-of-copies');
    const layoutDetectionMessageEl = byId('layout-detection-msg');

    byId('btn-update-documents').addEventListener('click', () => void updateDocuments({ urls: documentsUrls, nbCopies: numberOfCopiesEl.value }));
    byId('btn-layout-detection').addEventListener('click', () => void runLayoutDetection(documentsUrls, layoutDetectionMessageEl));
});