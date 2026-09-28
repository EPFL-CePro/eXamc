export {};

declare global {
    interface CeleryProgress {
        pending?: boolean;
        current: number;
        total: number;
        percent: number;
        description?: string;
    }

    interface CeleryProgressBarColors {
        success: string;
        error: string;
        progress: string;
        ignored: string;
    }

    type CeleryErrorHandler = (
        this: CeleryProgressBar,
        progressBarElement: HTMLElement,
        progressBarMessageElement: HTMLElement,
        excMessage?: string,
        data?: Response,
    ) => void;

    interface CeleryProgressBarOptions {
        progressBarId?: string;
        progressBarMessageId?: string;
        progressBarElement?: HTMLElement;
        progressBarMessageElement?: HTMLElement;
        resultElementId?: string;
        resultElement?: HTMLElement;

        onProgress?: (this: CeleryProgressBar, bar: HTMLElement, message: HTMLElement, progress: CeleryProgress) => void;
        onSuccess?: (this: CeleryProgressBar, bar: HTMLElement, message: HTMLElement, result: unknown) => void;
        onError?: CeleryErrorHandler;
        onTaskError?: (this: CeleryProgressBar, bar: HTMLElement, message: HTMLElement, excMessage: unknown) => void;
        onDataError?: CeleryErrorHandler;
        onRetry?: (this: CeleryProgressBar, bar: HTMLElement, message: HTMLElement, excMessage: string, retrySeconds: number) => void;
        onIgnored?: (this: CeleryProgressBar, bar: HTMLElement, message: HTMLElement, result: unknown) => void;
        onResult?: (this: CeleryProgressBar, resultElement: HTMLElement | null, result: unknown) => void;
        onNetworkError?: CeleryErrorHandler;
        onHttpError?: CeleryErrorHandler;

        pollInterval?: number;
        maxNetworkRetryAttempts?: number;
        barColors?: Partial<CeleryProgressBarColors>;
        defaultMessages?: Partial<{ waiting: string; started: string }>;
    }

    class CeleryProgressBar {
        constructor(progressUrl: string, options?: CeleryProgressBarOptions);

        progressUrl: string;
        progressBarElement: HTMLElement;
        progressBarMessageElement: HTMLElement;
        resultElement: HTMLElement | null;
        pollInterval: number;
        maxNetworkRetryAttempts: number;
        barColors: CeleryProgressBarColors;
        messages: { waiting: string; started: string };

        connect(): Promise<void>;
        onData(data: unknown): boolean | undefined;
        getMessageDetails(result: unknown): string;

        static getBarColorsDefault(): CeleryProgressBarColors;
        static initProgressBar(progressUrl: string, options?: CeleryProgressBarOptions): void;
    }
}