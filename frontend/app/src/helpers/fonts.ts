/** Font of the code editors: JetBrains Mono, then the usual monospace fallbacks. */
export function getCodeFontFamily(): string {
    void import('@fontsource-variable/jetbrains-mono').catch((error: unknown) => {
        throw new Error('JetBrains Mono could not be loaded', { cause: error });
    });

    return "'JetBrains Mono Variable', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
}

