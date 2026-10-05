import { ExamcError, EXCEPTION_MESSAGE_CONTACT_SUPPORT } from "./shared";

type FrontendErrorOptions = {
  type?: "generic";
  detail?: string;
};

export function buildFrontendError(...options: [FrontendErrorOptions, ...FrontendErrorOptions[]]): ExamcError {
    const messages = options.map(({ type = "generic", detail }) => {
        let message = "";

        switch (type) {
            case "generic":
                message = detail ? detail : "An unknown frontend error occured !";
                break;
        }

        return message;
    });

    messages.push(EXCEPTION_MESSAGE_CONTACT_SUPPORT);

    return new ExamcError(messages);
}