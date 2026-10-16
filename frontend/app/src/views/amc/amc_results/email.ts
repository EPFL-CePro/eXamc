import type { Api } from "datatables.net-dt";
import type { StudentRow } from "../amc_markings/types";
import { SimpleEditor } from "@examc/editors";

let pendingEmail: { subject: string; body: string } | null = null;

export async function initEmailEditor(
    options: {
        emailBodyEl: HTMLElement; 
        subjectInputEl: HTMLInputElement;
        sendTable: Api<StudentRow>;
    }
) {
    const { emailBodyEl, subjectInputEl, sendTable } = options;

    await SimpleEditor.create({ target: emailBodyEl });

    if (pendingEmail) {
        subjectInputEl.value = pendingEmail.subject;

        pendingEmail = null;
    }

    // The table was built while the dialog was hidden, so its column widths need recalculating.
    sendTable.columns.adjust();
}