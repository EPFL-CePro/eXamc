import 'vite/modulepreload-polyfill';
import {byId} from "@examc/helpers/dom.ts";
import { Modal } from 'bootstrap';

document.addEventListener('DOMContentLoaded', () => {
    const form = byId<HTMLFormElement>("upload-amc-project-form");
    const fileInput = byId<HTMLInputElement>("amc-project-zip-file");
    const fileLabel = byId<HTMLLabelElement>("amc-project-zip-file-label");

    fileInput.addEventListener("change", () => {
        const file = fileInput.files?.[0];
        if (!file) return;
        fileLabel.classList.add("selected");
        fileLabel.textContent = file.name;
    });

    form.addEventListener("submit", () => {
        const modalElement = byId("loadingModal");
        Modal.getOrCreateInstance(modalElement, { backdrop: "static", keyboard: false }).show();
    });
});
