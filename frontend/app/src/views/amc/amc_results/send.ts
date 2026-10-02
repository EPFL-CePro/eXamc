import { initEditor, getEditorContent } from '@examc/editor/index.ts';
import { byId } from '@examc/helpers/dom.ts';
import { parseJson, postText } from '@examc/helpers/http.ts';
import { getModal } from '@examc/helpers/modals.ts';
import { ModuleUninitialized } from './errors.ts';
import { showInfo } from './info.ts';
import { state } from './state.ts';
import { adjustSendTable, buildSendTable, selectedStudents } from './table.ts';
import type { SendDataResponse, SendResultResponse, SendUrls } from './types.ts';

let urls: SendUrls | null = null;

/** Sets the API endpoints. Called by index.ts once the DOM has loaded. */
export function initSend(endpoints: SendUrls): void {
    urls = endpoints;
}

const sendDialog = () => getModal({ type: 'local', element: byId('send-annotated-papers-dialog') });

/** Loads the students list and default email, then opens the send dialog. */
export async function openSendDialog(): Promise<void> {
    if (!urls) throw new ModuleUninitialized('send.ts', 'initSend');

    try {
        const data = parseJson<SendDataResponse>(await postText(urls.sendData, {})) ?? {};
        buildSendTable(data.data ?? []);

        // The default email is only applied when the editor is created,
        // so edits survive closing and reopening the dialog.
        if (!state.emailEditor) {
            state.pendingEmail = { subject: data.email_subject ?? '', body: data.email_text ?? '' };
        }
        sendDialog().show();
    } catch (error) {
        console.warn(error);
        showInfo('Failed to load the students list.');
    }
}

/** Runs once the send dialog is visible: creates the editor the first time, then fixes the table layout. */
export async function onSendDialogShown(): Promise<void> {
    if (!state.emailEditor) {
        const bodyField = byId<HTMLTextAreaElement>('email-body');
        if (state.pendingEmail) {
            byId<HTMLInputElement>('email-subject').value = state.pendingEmail.subject;
            bodyField.value = state.pendingEmail.body; // initial editor content
            state.pendingEmail = null;
        }
        state.emailEditor = await initEditor({ target: bodyField });
    }

    adjustSendTable();
}

/**
 * Form fields of the send form (csrf token, email column, subject...), as strings.
 *
 * @return {Record<string, string>} The fields.
 */
function sendFormFields(): Record<string, string> {
    const fields: Record<string, string> = {};
    for (const [key, value] of new FormData(byId<HTMLFormElement>('form-send-annotated-papers'))) {
        if (typeof value === 'string') fields[key] = value;
    }
    return fields;
}

/** Sends the annotated papers to the selected students, then shows the result. */
export async function sendAnnotatedPapers(): Promise<void> {
    if (!urls) throw new ModuleUninitialized('send.ts', 'initSend');
    if (!state.emailEditor) return; // dialog not ready yet

    const alert = byId('send_annotated_alert');
    const subject = byId<HTMLInputElement>('email-subject').value.trim();
    const body = getEditorContent({ editor: state.emailEditor, format: 'markdown' });

    if (subject === '' || body.trim() === '') {
        alert.style.visibility = 'visible';
        return;
    }
    alert.style.visibility = 'hidden';

    const emailColumn = byId<HTMLSelectElement>('email-column').value;
    const payload = {
        ...sendFormFields(),
        'selected-students': JSON.stringify(selectedStudents(emailColumn)),
        'email-body': body,
    };

    showInfo(
        "Sending annotated papers by email could take some time. A dialog will display when it's finished, "
        + 'and the results will also be visible in the send annotated papers modal!',
    );

    try {
        const result = parseJson<SendResultResponse>(await postText(urls.send, payload));
        if (!result) throw new Error('Send response was empty');
        const [sent, notSent, details] = result;

        const list = document.createElement('ul');
        list.append(...details.map((detail) => {
            const item = document.createElement('li');
            item.textContent = detail;
            return item;
        }));

        showInfo(
            `${sent} emails sent, ${notSent} not sent!`,
            document.createElement('br'),
            document.createElement('br'),
            list,
        );
        sendDialog().hide();
    } catch (error) {
        console.error(error);
        showInfo('Failed to send the annotated papers.');
    }
}