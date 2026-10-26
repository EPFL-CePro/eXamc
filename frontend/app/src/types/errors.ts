
/** A UserFacingError, as sent by the server: in a JSON error response, or in a Django message. */
export interface UserFacingError {
    title?: string;
    detail?: string;
    /** Rendered server-side from a template written in code, with escaped variables. */
    detail_html?: string;
    action_url?: string;
    action_label?: string;
}