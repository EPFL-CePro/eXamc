import { initBlackFridayPopup } from "./black-friday";

document.addEventListener("DOMContentLoaded", () => {
    // black friday gag
    if (new Date() < new Date('2026-12-01')) initBlackFridayPopup();
});
