import { describeFailure, failureJson } from "@examc/helpers/http.ts";

export function showResult(resultElement: HTMLElement, kind: "success" | "warning" | "danger", title: string,
                           details: string[] = []): void {
    resultElement.replaceChildren();
    resultElement.classList.remove("alert-success", "alert-warning", "alert-danger");
    resultElement.classList.add(`alert-${kind}`);

    // Texts are set with textContent: the errors quote the file content
    const heading = document.createElement("div");
    heading.className = "font-weight-bold";
    heading.textContent = title;
    resultElement.append(heading);

    if (details.length) {
        const list = document.createElement("ul");
        list.className = "mb-0 mt-1";
        for (const detail of details) {
            const item = document.createElement("li");
            item.textContent = detail;
            list.append(item);
        }
        resultElement.append(list);
    }
    // Dismissible: the result stays until closed or replaced
    const close = document.createElement("button");
    close.type = "button";
    close.className = "close";
    close.setAttribute("aria-label", "Close");
    close.innerHTML = '<span aria-hidden="true">&times;</span>';
    close.addEventListener("click", () => { resultElement.hidden = true; });
    resultElement.append(close);

    resultElement.hidden = false;
}

/**
 * Shows why a request failed: the errors listed by the server, or that the request could not be sent.
 * `title` says what was not done.
 */
export function showFailure(resultElement: HTMLElement, error: unknown, title: string): void {
    const failure = describeFailure(error);
    if (failure.status === 0) {
        console.error(title, error);
        showResult(resultElement, "danger", "The request could not be sent: please check your connection and try again.");
        return;
    }

    const { errors } = failureJson<{ errors?: string[] }>(failure);
    showResult(resultElement, "danger", title, errors ?? [`Server error (${failure.status}).`]);
}
