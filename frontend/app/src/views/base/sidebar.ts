/** Shows the X while the drawer is open or opening, and the bars otherwise. */
export function setSidebarToggleOpen(open: boolean, toggleEl: HTMLElement): void {
    toggleEl.querySelector('[data-sidebar-icon="open"]')?.classList.toggle("d-none", open);
    toggleEl.querySelector('[data-sidebar-icon="close"]')?.classList.toggle("d-none", !open);
    toggleEl.setAttribute("aria-expanded", String(open));
}