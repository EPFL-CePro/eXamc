/**
 * Moves options from one list to the other. Disabled options (exams without questions) stay where they are.
 *
 * @param {HTMLSelectElement} source - The list to take them from.
 * @param {HTMLSelectElement} target - The list to put them in.
 * @param {boolean} all - Every option, or only the selected ones.
 */
function moveOptions(source: HTMLSelectElement, target: HTMLSelectElement, all: boolean): void {
    for (const option of [...(all ? source.options : source.selectedOptions)]) {
        if (option.disabled) continue;
        option.selected = false;
        target.append(option);
    }
}

/**
 * The common exams picker of the overall exam: available exams on the left, selected ones on the right.
 * The form is submitted normally, with every exam of the right list.
 *
 * @param {HTMLFormElement} form - The common exams form.
 */
export function initCommonExams(form: HTMLFormElement): void {
    const from = form.querySelector<HTMLSelectElement>('select[data-list="from"]')!;
    const to = form.querySelector<HTMLSelectElement>('select[data-list="to"]')!;

    form.addEventListener('click', (event) => {
        const button = (event.target as Element).closest<HTMLElement>('[data-move]');
        switch (button?.dataset['move']) {
            case 'to-all': moveOptions(from, to, true); break;
            case 'to': moveOptions(from, to, false); break;
            case 'from': moveOptions(to, from, false); break;
            case 'from-all': moveOptions(to, from, true); break;
        }
    });
    from.addEventListener('dblclick', () => moveOptions(from, to, false));
    to.addEventListener('dblclick', () => moveOptions(to, from, false));

    // A multiple select only submits its selected options: select the whole right list.
    form.addEventListener('submit', () => {
        for (const option of from.options) option.selected = false;
        for (const option of to.options) option.selected = true;
    });
}