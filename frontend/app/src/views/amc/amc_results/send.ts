import { parseJson, postText } from '@examc/helpers/http.ts';
import { LoadingModal } from '@examc/modals';

import { ModuleUninitialized } from './errors.ts';
import { showInfo } from './info.ts';
import { SendPapersModal } from './send-modal.ts';
import type { EmailDraft, SendDataResponse, SendRequest, SendResultResponse, SendUrls } from './types.ts';

let urls: SendUrls | null = null;

/** The email left in the dialog when it was last closed without sending. */
let draft: EmailDraft | null = null;

/** The result of the last send, shown once the dialog is closed. */
let sendResult: (Node | string)[] | null = null;

/** Sets the API endpoints. Called by index.ts once the DOM has loaded. */
export function initSend(endpoints: SendUrls): void {
    urls = endpoints;
}

/** Loads the students list and default email, then opens the send dialog. */
export async function openSendDialog(): Promise<void> {
    if (!urls) throw new ModuleUninitialized('send.ts', 'initSend');
    const url = urls.sendData;

    let data: SendDataResponse;
    try {
        data = parseJson<SendDataResponse>(await new LoadingModal(() => postText(url, {})).result) ?? {};
    } catch (error) {
        console.warn(error);
        showInfo('Failed to load the students list.');
        return;
    }

    new SendPapersModal({
        rows: data.data ?? [],
        // The server's default email, unless the user already started writing one
        draft: draft ?? { subject: data.email_subject ?? '', body: data.email_text ?? '' },
        onSend: sendAnnotatedPapers,
        onClose: (left) => {
            draft = left;
            if (sendResult) showInfo(...sendResult);
            sendResult = null;
        },
    }).show();
}

/**
 * Sends the annotated papers. The result is shown once the dialog is closed.
 *
 * @param {SendRequest} request - What to send, and to whom.
 * @throws {Error} If the request fails: the dialog then stays open.
 */
async function sendAnnotatedPapers(request: SendRequest): Promise<void> {
    if (!urls) throw new ModuleUninitialized('send.ts', 'initSend');

    const result = parseJson<SendResultResponse>(await postText(urls.send, {
        'email-column': request.emailColumn,
        'email-subject': request.subject,
        'email-body': request.body,
        'selected-students': JSON.stringify(request.students),
    }));
    if (!result) throw new Error('Send response was empty');

    const [sent, notSent, details] = result;
    const list = document.createElement('ul');
    list.append(...details.map((detail) => {
        const item = document.createElement('li');
        item.textContent = detail;
        return item;
    }));

    sendResult = [`${sent} emails sent, ${notSent} not sent!`, list];
}