import "./main.scss";

import { Tooltip } from "bootstrap";
import { initTooltips } from "./tooltips";
import { byId } from "@examc/helpers/dom";
import { setSidebarToggleOpen } from "./sidebar";


// The page on load (without htmx, or before htmx processes it), then each piece of content htmx inserts.
document.addEventListener("DOMContentLoaded", () => {
    const sidebar = byId("sidebar-container");
    const toggle = byId("sidebar-toggle");

    // sidebar mgmt
    sidebar.addEventListener("show.bs.offcanvas", () => setSidebarToggleOpen(true, toggle));
    sidebar.addEventListener("hide.bs.offcanvas", () => setSidebarToggleOpen(false, toggle));

    // tooltips init
    initTooltips(document.body);
});

document.addEventListener("htmx:load", (event: Event) => {
    if (event.target instanceof Element) initTooltips(event.target);
});

// htmx fires this for each element it removes, descendants included: hides and removes their tooltips.
document.addEventListener("htmx:beforeCleanupElement", (event: Event) => {
    if (event.target instanceof Element) Tooltip.getInstance(event.target)?.dispose();
});