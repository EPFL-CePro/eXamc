import { parseJson, postText } from '@examc/helpers/http.ts';

import { ModuleUninitialized } from './errors.ts';
import { SendPapersModal } from './send-modal.ts';
import type { EmailDraft, SendDataResponse, SendRequest, SendResultResponse, SendUrls } from './types.ts';

let urls: SendUrls | null = null;

/** The email left in the dialog when it was last closed without sending. */
let draft: EmailDraft | null = null;

/** Sets the API endpoints. Called by index.ts once the DOM has loaded. */
export function initSend(endpoints: SendUrls): void {
    urls = endpoints;
}

/** The outcome of a send: counts, and one line per student. */
export interface SendResult {
    sent: number;
    notSent: number;
    details: string[];
}

/**
 * Loads the students list and default email, then opens the send dialog.
 *
 * @param {(result: SendResult) => void} onSent - Called once the papers are sent and the dialog is closed.
 * @throws {Error} If the students list can't be loaded.
 */
export async function openSendDialog(onSent: (result: SendResult) => void): Promise<void> {
    if (!urls) throw new ModuleUninitialized('send.ts', 'initSend');

    const data = parseJson<SendDataResponse>(await postText(urls.sendData, {})) ?? {};
    let result: SendResult | null = null;

    new SendPapersModal({
        rows: data.data ?? [],
        // The server's default email, unless the user already started writing one
        draft: draft ?? { subject: data.email_subject ?? '', body: data.email_text ?? '' },
        onSend: async (request) => {
            result = await sendAnnotatedPapers(request);
        },
        onClose: (left) => {
            draft = left;
            if (result) onSent(result);
        },
    }).show();
}

/**
 * Sends the annotated papers.
 *
 * @throws {Error} If the request fails: the dialog then stays open.
 */
async function sendAnnotatedPapers(request: SendRequest): Promise<SendResult> {
    if (!urls) throw new ModuleUninitialized('send.ts', 'initSend');

    const response = parseJson<SendResultResponse>(await postText(urls.send, {
        'email-column': request.emailColumn,
        'email-subject': request.subject,
        'email-body': request.body,
        'selected-students': JSON.stringify(request.students),
    }));
    if (!response) throw new Error('Send response was empty');

    const [sent, notSent, details] = response;
    return { sent, notSent, details };
}
