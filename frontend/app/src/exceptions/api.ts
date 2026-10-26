import { ExamcError, EXCEPTION_MESSAGE_CONTACT_SUPPORT } from "./shared";


type ApiErrorOptions = {
    type?: "generic" | "wrong-api-response";
    detail?: string;  
};

export function buildApiError(...options: [ApiErrorOptions, ...ApiErrorOptions[]]): ExamcError {
    const messages = options.map(({ type = "generic", detail }) => {
        let message = "";

        switch (type) {
            case "generic":
                message = detail ? detail : "An unknown API error occured !";
                break;
            case "wrong-api-response": 
                message = `The API returned an unexpected response format${detail ? `: ${detail}` : ""}.`;
                break;
        }

        return message;
    });

    messages.push(EXCEPTION_MESSAGE_CONTACT_SUPPORT);

    return new ExamcError(messages);
}
