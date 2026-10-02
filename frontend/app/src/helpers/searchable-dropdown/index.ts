import { Dropdown } from 'bootstrap';

import './main.scss';

/** One choice of a searchable dropdown. */
export interface SearchableDropdownChoice {
    value: string;
    label: string;
    /** Extra text matched by the search but not displayed (e.g. an id or email). */
    keywords?: string;
    disabled?: boolean;
}

export interface SearchableDropdownOptions {
    /** The choices. The same array can be shared by many dropdowns; it is never modified. */
    choices: SearchableDropdownChoice[];
    /** The value selected initially. Defaults to the first choice. */
    selected?: string;
    /** Called when the user picks another value (not when setValue() is called). */
    onChange?: (value: string) => void;
    /** Classes of the toggle button. Default: 'btn btn-dark btn-sm'. */
    buttonClass?: string;
    /** Placeholder of the search box. Default: 'Search...'. */
    searchPlaceholder?: string;
    /** Accessible label of the search box. Default: the search placeholder. */
    searchLabel?: string;
    /** Text shown when nothing matches. Default: 'No match'. */
    emptyText?: string;
    /** Label of the button when the value matches no choice. Default: ''. */
    placeholder?: string;
}

export interface SearchableDropdown {
    /** The element to insert in the page. */
    element: HTMLElement;
    /** The selected value. */
    getValue: () => string;
    /** Selects a value without calling onChange. */
    setValue: (value: string) => void;
    /** Releases the Bootstrap dropdown; call before removing the element. */
    dispose: () => void;
}

/**
 * Lowercases and strips accents, so the search ignores case and diacritics.
 *
 * @param {string} text - The text.
 * @returns {string} The normalized text.
 */
const normalize = (text: string): string => text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();

/**
 * Creates a Bootstrap 5 dropdown with a search box, a jQuery-free replacement for
 * bootstrap-select's live-search select. Menu items are only rendered while the menu is open,
 * so pages with many dropdowns and long choice lists stay light.
 *
 * Size it with the CSS variables --searchable-dropdown-width (menu and max button width)
 * and --searchable-dropdown-max-height (scrolling list).
 *
 * @param {SearchableDropdownOptions} options - The choices, initial value, callback and labels.
 * @returns {SearchableDropdown} The element and its controls.
 */
export function createSearchableDropdown(options: SearchableDropdownOptions): SearchableDropdown {
    const {
        choices,
        onChange,
        buttonClass = 'btn btn-dark btn-sm',
        searchPlaceholder = 'Search...',
        searchLabel = searchPlaceholder,
        emptyText = 'No match',
        placeholder = '',
    } = options;

    let value = options.selected ?? choices[0]?.value ?? '';
    let searchIndex: string[] | null = null; // normalized label + keywords, built on first open

    const wrapper = document.createElement('div');
    wrapper.className = 'dropdown searchable-dropdown';

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = `${buttonClass} dropdown-toggle`;
    toggle.setAttribute('aria-expanded', 'false');

    const menu = document.createElement('div');
    menu.className = 'dropdown-menu searchable-dropdown-menu';

    const searchBox = document.createElement('div');
    searchBox.className = 'searchable-dropdown-search';
    const search = document.createElement('input');
    search.type = 'search';
    search.className = 'form-control form-control-sm';
    search.placeholder = searchPlaceholder;
    search.setAttribute('aria-label', searchLabel);
    searchBox.append(search);

    const list = document.createElement('div');
    list.className = 'searchable-dropdown-list';

    menu.append(searchBox, list);
    wrapper.append(toggle, menu);

    // No data-bs-toggle attribute: clicks, outside clicks and keys are handled below, so the dropdown
    // doesn't depend on Bootstrap's document-wide data API (which a second Bootstrap copy on the page,
    // e.g. a <script> bundle, would also run, opening and closing the menu on the same click).
    const dropdown = new Dropdown(toggle, {
        autoClose: false, // closing is handled below: outside clicks, Escape, focus leaving
        // Fixed positioning keeps the menu from being clipped by scrolling containers such as modals.
        popperConfig: (config) => ({ ...config, strategy: 'fixed' }),
    });

    const isOpen = (): boolean => menu.classList.contains('show');

    /** Closes the menu when a click lands outside the dropdown. */
    const onDocumentClick = (event: MouseEvent): void => {
        if (!wrapper.contains(event.target as Node)) dropdown.hide();
    };

    /** Shows the selected choice's label on the button. */
    function updateToggle(): void {
        const label = choices.find((choice) => choice.value === value)?.label ?? placeholder;
        toggle.textContent = label;
        toggle.title = label;
    }

    /**
     * Renders the choices matching a search.
     *
     * @param {string} query - The search text.
     */
    function render(query: string): void {
        searchIndex ??= choices.map((choice) => normalize(`${choice.label} ${choice.keywords ?? ''}`));
        const needle = normalize(query.trim());

        const items = choices.flatMap((choice, index) => {
            if (needle && !searchIndex?.[index]?.includes(needle)) return [];

            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'dropdown-item';
            item.dataset['value'] = choice.value;
            item.textContent = choice.label;
            item.disabled = choice.disabled ?? false;
            if (choice.value === value) {
                item.classList.add('active');
                item.setAttribute('aria-current', 'true');
            }
            return [item];
        });

        if (items.length > 0) {
            list.replaceChildren(...items);
        } else {
            const empty = document.createElement('span');
            empty.className = 'dropdown-item-text text-muted';
            empty.textContent = emptyText;
            list.replaceChildren(empty);
        }
    }

    /**
     * Selects a value picked by the user and closes the menu.
     *
     * @param {string} newValue - The picked value.
     */
    function choose(newValue: string): void {
        dropdown.hide();
        toggle.focus();
        if (newValue === value) return;

        value = newValue;
        updateToggle();
        onChange?.(value);
    }

    /**
     * The value of the first enabled item in the list, if any.
     *
     * @returns {HTMLButtonElement | null} The item.
     */
    const firstItem = (): HTMLButtonElement | null =>
        list.querySelector<HTMLButtonElement>('.dropdown-item:not(:disabled)');

    toggle.addEventListener('click', (event) => {
        event.preventDefault();
        dropdown.toggle();
    });

    // Escape closes the menu (and not the modal it may be in); ArrowDown on the button opens it.
    wrapper.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && isOpen()) {
            event.preventDefault();
            event.stopPropagation();
            dropdown.hide();
            toggle.focus();
        } else if (event.key === 'ArrowDown' && event.target === toggle && !isOpen()) {
            event.preventDefault();
            dropdown.show();
        }
    });

    // Tabbing out of the dropdown closes it.
    wrapper.addEventListener('focusout', (event) => {
        if (isOpen() && !wrapper.contains(event.relatedTarget as Node | null)) dropdown.hide();
    });

    toggle.addEventListener('show.bs.dropdown', () => {
        document.addEventListener('click', onDocumentClick);
        search.value = '';
        render('');
    });
    toggle.addEventListener('shown.bs.dropdown', () => {
        search.focus();
        list.querySelector('.active')?.scrollIntoView({ block: 'nearest' });
    });
    toggle.addEventListener('hidden.bs.dropdown', () => {
        document.removeEventListener('click', onDocumentClick);
        list.replaceChildren(); // free the items
    });

    search.addEventListener('input', () => render(search.value));
    search.addEventListener('keydown', (event) => {
        const first = firstItem();
        if (event.key === 'Enter') {
            event.preventDefault();
            if (first?.dataset['value'] !== undefined) choose(first.dataset['value']);
        } else if (event.key === 'ArrowDown' && first) {
            event.preventDefault();
            first.focus(); // the list's keydown handler moves between items from there
        }
    });

    // ArrowUp / ArrowDown move between items; ArrowUp on the first one goes back to the search box.
    list.addEventListener('keydown', (event) => {
        if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
        event.preventDefault();

        const items = Array.from(list.querySelectorAll<HTMLButtonElement>('.dropdown-item:not(:disabled)'));
        const index = items.indexOf(event.target as HTMLButtonElement);
        const next = items[index + (event.key === 'ArrowDown' ? 1 : -1)];
        if (next) next.focus();
        else if (event.key === 'ArrowUp') search.focus();
    });

    list.addEventListener('click', (event) => {
        const item = (event.target as Element).closest<HTMLButtonElement>('[data-value]');
        if (item && !item.disabled && item.dataset['value'] !== undefined) choose(item.dataset['value']);
    });

    updateToggle();

    return {
        element: wrapper,
        getValue: () => value,
        setValue: (newValue: string) => {
            value = newValue;
            updateToggle();
        },
        dispose: () => {
            document.removeEventListener('click', onDocumentClick);
            dropdown.dispose();
        },
    };
}