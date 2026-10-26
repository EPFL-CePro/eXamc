import { EditorModal } from "@examc/modals/editor";

export async function openGradingHelp(button: HTMLButtonElement): Promise<void> {
    const groupPk: string | undefined = button.dataset.gradingHelpGroup;
    const urls = button.closest<HTMLElement>("[data-grading-help-load-url]")?.dataset;
    const csrfToken: string | undefined = button.closest("form")
        ?.querySelector<HTMLInputElement>('input[name="csrfmiddlewaretoken"]')?.value;

    if (!groupPk || !urls?.gradingHelpLoadUrl || !urls.gradingHelpSaveUrl || !csrfToken) {
        throw new Error("A grading help button needs a group id, the load and save URLs and a CSRF token.");
    }
    const { gradingHelpLoadUrl: loadUrl, gradingHelpSaveUrl: saveUrl } = urls;

    // Prevents opening the modal twice while the content is loading.
    button.disabled = true;
    try {
        const body = new FormData();
        body.set("csrfmiddlewaretoken", csrfToken);
        body.set("group_pk", groupPk);

        const response = await fetch(loadUrl, { method: "POST", body });
        if (!response.ok) throw new Error(`Could not load the grading help (HTTP ${response.status}).`);
        const content: string = await response.text();

        new EditorModal().edit({
            title: "Grading help",
            content,
            format: "markdown",
            onSave: async (edited) => {
                const saveBody = new FormData();
                saveBody.set("csrfmiddlewaretoken", csrfToken);
                saveBody.set("group_pk", groupPk);
                saveBody.set("grading_help", edited);

                const saveResponse = await fetch(saveUrl, { method: "POST", body: saveBody });
                if (!saveResponse.ok) throw new Error(`Could not save the grading help (HTTP ${saveResponse.status}).`);
            },
        });
    } finally {
        button.disabled = false;
    }
}