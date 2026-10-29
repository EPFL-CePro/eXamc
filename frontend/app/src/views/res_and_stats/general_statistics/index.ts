import { manageTabs } from "@examc/helpers/tabs";

document.addEventListener("DOMContentLoaded", () => {
    manageTabs({ tabListSelector: "#general-stats-tabs" });
});