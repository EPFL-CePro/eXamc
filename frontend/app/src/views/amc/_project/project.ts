import { postText } from '@examc/helpers/http.ts';
import { type CodeFolder, CodeEditorModal } from '@examc/modals/code.ts';

/** A folder of the AMC project, as built by path_to_dict. */
export interface FolderNode {
    text: string;
    href: string;
    nodes?: FolderNode[];
}

/** The LaTeX files of a folder, each as [file name, path relative to the AMC project]. */
export interface FolderFiles {
    folder: string;
    files: [string, string][];
}

export interface SourceFilesUrls {
    editFile: string;
    saveFile: string;
    csrfToken: string;
}

/**
 * Merges the folder tree and the files of each folder into one tree.
 *
 * @param {FolderNode} node - A folder of the project.
 * @param {FolderFiles[]} folderFiles - The LaTeX files of every folder.
 * @return {CodeFolder} The folder, with its subfolders and files.
 */
function toCodeFolder(node: FolderNode, folderFiles: FolderFiles[]): CodeFolder {
    const files = folderFiles.find((candidate) => candidate.folder === node.text)?.files ?? [];
    return {
        name: node.text,
        folders: (node.nodes ?? []).map((child) => toCodeFolder(child, folderFiles)),
        files: files.map(([name, path]) => ({ name, path })),
    };
}

/**
 * Opens the LaTeX source files of the AMC project in the code editor dialog.
 *
 * @param {SourceFilesUrls} urls - The URLs used to read and save files.
 * @param {FolderNode | null} projectDir - The folder tree of the AMC project.
 * @param {FolderFiles[]} folderFiles - The LaTeX files of every folder.
 */
export function openSourceFiles(urls: SourceFilesUrls, projectDir: FolderNode | null, folderFiles: FolderFiles[]): void {
    if (!projectDir) return;

    void new CodeEditorModal({
        title: 'Source LaTeX files',
        language: 'latex',
        root: toCodeFolder(projectDir, folderFiles),
        loadFile: (filepath) => postText(urls.editFile, { csrfmiddlewaretoken: urls.csrfToken, filepath }),
        saveFile: (filepath, data) => postText(urls.saveFile, { csrfmiddlewaretoken: urls.csrfToken, data, filepath }),
    }).open();
}