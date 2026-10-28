import { initDefaultTab } from "./default-tab";
import { initManualTab } from "./manual-tab";
import { byId, requireData } from "@examc/helpers/dom.ts";
import { manageTabs } from "@examc/helpers/tabs.ts";

import "./room-plan.scss";

document.addEventListener("DOMContentLoaded", () => {
    const page = byId<HTMLElement>("rooms-plans-page");
    
    const defaultPane = page.querySelector<HTMLElement>('[data-room-plan-tab="default"]');
    const manualPane = page.querySelector<HTMLElement>('[data-room-plan-tab="manual"]');

    const template = byId<HTMLTemplateElement>("room-plan-template");
    const mapUrl = requireData(page,"mapUrl");

    manageTabs({ tabId: page.dataset.currentTab ?? "" });


    // ---------- Default tab ----------

    if (defaultPane) {
        const select = defaultPane.querySelector<HTMLSelectElement>("select[data-room-select]");
        const list = defaultPane.querySelector<HTMLElement>(".room-plans");
        const form = byId<HTMLFormElement>("default-form");

        if (!select || !list || !form) {
            console.error("Room plan (default tab): an element of the page is missing.", { select, list, form });
        } else {
            initDefaultTab({
                select,
                list,
                form,
                skippingInputs: Array.from(form.querySelectorAll<HTMLInputElement>('input[name="skipping_option"]')),
                numberingInputs: Array.from(form.querySelectorAll<HTMLInputElement>('input[name="numbering_option"]')),
                fillAllSeats: form.querySelector<HTMLInputElement>('input[name="fill_all_seats"]'),
                specialFileRow: byId<HTMLElement>("div-special_file"),
                lastSeatNumberRow: byId<HTMLElement>("div-last_seat_number"),
            }, template, mapUrl);
        }
    }

    // ---------- Manual tab ----------

    if (manualPane) {
        const select = manualPane.querySelector<HTMLSelectElement>("select[data-room-select]");
        const list = manualPane.querySelector<HTMLElement>(".room-plans");
        const form = byId<HTMLFormElement>("manual-form");
        const prefixInput = byId<HTMLInputElement>("prefix-input");
        const downloadButton = byId<HTMLButtonElement>("btn-download-plans");
        const undoButton = byId<HTMLButtonElement>("btn-undo-label");
        const exportLayout = byId<HTMLElement>("export-layout");

        if (!select || !list) {
            console.error("Room plan (manual tab): an element of the page is missing.", {
                select, list,
            });
        } else {
            initManualTab({
                select,
                list,
                form,
                // The field name depends on the form's prefix (e.g. "manual-numbering_option")
                numberingInputs: Array.from(
                    form.querySelectorAll<HTMLInputElement>('input[type="radio"][name$="numbering_option"]'),
                ),
                prefixInput,
                downloadButton,
                undoButton,
                exportLayout,
            }, template, mapUrl, page.dataset.fileName || "plan");
        }
    }
});