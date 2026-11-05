/** Form fields; an array value appends the key once per item (e.g. 'pages_list[]'). */
export type FormFields = Record<string, boolean | number | string | readonly string[]>;
