import { manageTabs } from '@examc/helpers/tabs';
import { attachGradingSchemePagesGroupEditors, syncGradingSchemePagesGroupEditors } from "./inline-editors.ts";

document.addEventListener('DOMContentLoaded', () => {
    manageTabs({ tabListSelector: "#review-settings-tabs" });
});

// Content swapped into the panel by htmx.
document.addEventListener("htmx:load", () => {
    // initializes the editors for descriptions
    const textAreas = document.querySelectorAll<HTMLTextAreaElement>("textarea[data-simple-editor]");
    attachGradingSchemePagesGroupEditors(textAreas);
});

// Regular form submissions.
document.addEventListener("submit", (event: Event) => {
    if (event.target instanceof HTMLFormElement) syncGradingSchemePagesGroupEditors(event.target);
}, true);

// htmx requests: "htmx:confirm" fires before htmx collects the form's values.
document.addEventListener("htmx:confirm", (event: Event) => {
    if (!(event.target instanceof Element)) return;
    syncGradingSchemePagesGroupEditors(event.target.closest("form") ?? event.target);
});
