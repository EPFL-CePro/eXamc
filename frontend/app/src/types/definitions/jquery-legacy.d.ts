export {};

declare global {
    /**
     * The little of jQuery (loaded by base.html) that the preparation page still uses. @types/jquery is not
     * loaded on purpose: its global types break the DataTables ones.
     */
    interface LegacyJQuery {
        hide(): LegacyJQuery;
        show(): LegacyJQuery;
        toggle(display?: boolean): LegacyJQuery;
        empty(): LegacyJQuery;
        html(html: string): LegacyJQuery;
        text(text: string): LegacyJQuery;
        val(value: string): LegacyJQuery;
        attr(name: string, value: string): LegacyJQuery;
        css(name: string, value: string): LegacyJQuery;
        append(content: LegacyJQuery): LegacyJQuery;
        on(event: string, handler: () => void): LegacyJQuery;
        modal(action: "show" | "hide"): LegacyJQuery;
        serialize(): string;
    }

    interface LegacyAjaxSettings {
        url: string;
        type: string;
        data: object | string;
        headers: Record<string, string>;
        beforeSend?: () => void;
        complete?: () => void;
        success?: (data: never) => void;
        error?: (xhr: unknown) => void;
    }

    const $: {
        (selector: string | Element): LegacyJQuery;
        ajax(settings: LegacyAjaxSettings): unknown;
    };
}
