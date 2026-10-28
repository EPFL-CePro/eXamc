import { initRoomPreviews } from "./room-previews";

export interface DefaultTabElements {
    select: HTMLSelectElement;
    list: HTMLElement;
    form: HTMLFormElement;
    skippingInputs: HTMLInputElement[];
    numberingInputs: HTMLInputElement[];
    fillAllSeats: HTMLInputElement | null;
    specialFileRow: HTMLElement | null;
    lastSeatNumberRow: HTMLElement | null;
}

/** Default tab: room previews + show/hide form rows depending on the options. */
export function initDefaultTab(el: DefaultTabElements, template: HTMLTemplateElement, mapUrl: string): void {
    initRoomPreviews(el.select, el.list, template, mapUrl);

    const checkedValue = (inputs: HTMLInputElement[]): string | undefined =>
        inputs.find((input) => input.checked)?.value;

    /** The special file is needed when skipping seats or using special numbering. */
    const showHideSpecialFile = (): void => {
        const show = checkedValue(el.skippingInputs) === "skip" || checkedValue(el.numberingInputs) === "special";
        el.specialFileRow?.classList.toggle("d-none", !show);
    };

    /** "Last seat number" is irrelevant when all seats are filled. */
    const showHideLastNumber = (): void => {
        el.lastSeatNumberRow?.classList.toggle("d-none", Boolean(el.fillAllSeats?.checked));
    };

    el.form.addEventListener("change", (event) => {
        if (!(event.target instanceof HTMLInputElement)) return;

        if (el.skippingInputs.includes(event.target) || el.numberingInputs.includes(event.target)) {
            showHideSpecialFile();
        } else if (event.target === el.fillAllSeats) {
            showHideLastNumber();
        }
    });

    // Initial state (also correct after a POST re-render)
    showHideSpecialFile();
    showHideLastNumber();
}