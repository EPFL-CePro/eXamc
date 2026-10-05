export const EXCEPTION_MESSAGE_CONTACT_SUPPORT = " If you don't know what this means, please contact CEPro's eXamc team for support and include this message in your request.";

export class ExamcError extends Error {
    /** Store multiple error messages in a single Error */
    messages: string[];


    constructor(messages: string[]) {
        super();
        this.messages = messages;

        Object.setPrototypeOf(this, ExamcError.prototype);
    }
};

/**
 * Verify that any given value is of the type ExamcError
 * @param value
 * @returns asserts that value is an instance of ExamcError
 */
export function isExamcError(value: unknown): value is ExamcError {
    return value instanceof ExamcError;
}