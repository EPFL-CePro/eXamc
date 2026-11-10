/**
 * The handle's markup: a line, the arrows icon, and a line, along its orientation.
 *
 * @param {boolean} vertical - A vertical bar (resizes the width), else a horizontal one (the height).
 * @return {string} The markup.
 */
export function template(vertical: boolean): string {
    const line = vertical ? '<div class="vr flex-grow-1 m-auto"></div>' : '<hr class="flex-grow-1 m-0">';
    const arrows = vertical ? 'fa-arrows-left-right' : 'fa-arrows-up-down';
    return `${line}<i class="fa-solid ${arrows}" aria-hidden="true"></i>${line}`;
}

/** Classes of the handle element itself. */
export function hostClasses(vertical: boolean): string[] {
    const classes = ['d-flex', 'align-items-center', 'gap-2', 'flex-shrink-0', 'text-body-secondary'];
    return vertical ? [...classes, 'flex-column'] : classes;
}