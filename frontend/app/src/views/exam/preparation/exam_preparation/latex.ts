import { URLS } from "./config.ts";
import { ajaxGet, ajaxPost, hideModal, showModal } from "./ajax.ts";

// Edit LaTeX file management

function byIdOrThrow<T extends HTMLElement = HTMLElement>(id: string): T {
    const element = document.getElementById(id);
    if (!element) throw new Error(`#${id} not found`);
    return element as T;
}

export function openEditLaTeXFileDialog(type: string): void {
    ajaxGet<string>(URLS.editLatexFile, { type }, {
        success: (data) => {
            byIdOrThrow<HTMLTextAreaElement>("latex_source_text").value = (JSON.parse(data) as string[])[1] ?? "";
            byIdOrThrow("edit_latex_file_modal_title").innerText = "Edit " + type;
            byIdOrThrow("edit_latex_file_type").innerText = type;
            showModal("#edit_latex_file_modal");
        },
        error: (error) => {
            console.log(error);
        },
    });
}

export function saveEditedLaTeXFile(): void {
    const data = {
        source: byIdOrThrow<HTMLTextAreaElement>("latex_source_text").value,
        type: byIdOrThrow("edit_latex_file_type").innerText,
    };

    ajaxPost(URLS.saveLatexFile, data, {
        success: () => {
            hideModal("#edit_latex_file_modal");
        },
        error: (error) => {
            console.log(error);
        },
    });
}

// LaTeX packages management

interface PackagesResponse {
    latex_available_packages?: (string | { name?: string })[];
    used_packages?: string[];
}

let latexAvailablePackages: string[] = [];
let currentUsedPackages: string[] = [];

function uniq<T>(arr: T[]): T[] {
    return [...new Set(arr)];
}

function sortStrings(arr: string[]): string[] {
    return [...arr].sort((a, b) => a.localeCompare(b));
}

function normalizeAvailablePackages(rawPackages: PackagesResponse["latex_available_packages"]): string[] {
    return uniq(
        (rawPackages ?? [])
            .map((pkg) => (typeof pkg === "string" ? pkg : pkg.name))
            .filter((name): name is string => Boolean(name)),
    );
}

function normalizeUsedPackages(rawPackages: string[] | undefined): string[] {
    return uniq((rawPackages ?? []).filter(Boolean));
}

function renderUsedPackages(): void {
    const container = byIdOrThrow("used_latex_packages_list");
    container.innerHTML = "";

    if (!currentUsedPackages.length) {
        container.innerHTML = `<div class="latex-empty-state">No package selected.</div>`;
        return;
    }

    sortStrings(currentUsedPackages).forEach((pkg) => {
        const chip = document.createElement("div");
        chip.className = "latex-chip";

        const label = document.createElement("span");
        label.textContent = pkg;

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "latex-chip-remove";
        removeBtn.innerHTML = "&times;";
        removeBtn.title = `Remove ${pkg}`;
        removeBtn.onclick = () => removeUsedPackage(pkg);

        chip.appendChild(label);
        chip.appendChild(removeBtn);
        container.appendChild(chip);
    });
}

function getFilteredAvailablePackages(searchText = ""): string[] {
    const usedSet = new Set(currentUsedPackages);
    const query = searchText.trim().toLowerCase();

    return sortStrings(
        latexAvailablePackages.filter((pkg) => {
            if (usedSet.has(pkg)) return false;
            if (!query) return true;
            return pkg.toLowerCase().includes(query);
        }),
    ).slice(0, 50);
}

function renderPackageSearchResults(searchText = ""): void {
    const container = byIdOrThrow("latex_package_search_results");
    const results = getFilteredAvailablePackages(searchText);

    if (!results.length) {
        container.style.display = "none";
        container.innerHTML = "";
        return;
    }

    container.innerHTML = "";

    results.forEach((pkg) => {
        const item = document.createElement("div");
        item.className = "latex-search-item";
        item.textContent = pkg;
        item.onclick = () => {
            addUsedPackage(pkg);
            byIdOrThrow<HTMLInputElement>("latex_package_search").value = "";
            renderPackageSearchResults("");
        };
        container.appendChild(item);
    });

    container.style.display = "block";
}

function addUsedPackage(pkg: string): void {
    if (!pkg || currentUsedPackages.includes(pkg)) return;
    currentUsedPackages.push(pkg);
    currentUsedPackages = uniq(currentUsedPackages);
    renderUsedPackages();
}

function removeUsedPackage(pkg: string): void {
    currentUsedPackages = currentUsedPackages.filter((p) => p !== pkg);
    renderUsedPackages();
    renderPackageSearchResults(byIdOrThrow<HTMLInputElement>("latex_package_search").value);
}

function bindLatexPackageSearch(): void {
    const input = byIdOrThrow<HTMLInputElement>("latex_package_search");
    const results = byIdOrThrow("latex_package_search_results");

    input.oninput = () => {
        renderPackageSearchResults(input.value);
    };

    input.onfocus = () => {
        renderPackageSearchResults(input.value);
    };

    document.addEventListener("click", (event) => {
        const target = event.target as Node;
        if (!input.contains(target) && !results.contains(target)) {
            results.style.display = "none";
        }
    });
}

export function openEditLaTeXPackagesDialog(type: string): void {
    ajaxGet<string | PackagesResponse>(URLS.editLatexPackages, { type }, {
        success: (response) => {
            const data: PackagesResponse = typeof response === "string" ? (JSON.parse(response) as PackagesResponse) : response;

            latexAvailablePackages = normalizeAvailablePackages(data.latex_available_packages);
            currentUsedPackages = normalizeUsedPackages(data.used_packages);

            bindLatexPackageSearch();
            renderUsedPackages();
            renderPackageSearchResults("");

            showModal("#edit_latex_packages_modal");
        },
        error: (error) => {
            console.log(error);
        },
    });
}

export function saveEditedLaTeXPackages(): void {
    const data = {
        new_used_packages: currentUsedPackages,
    };

    ajaxPost(URLS.saveLatexPackages, data, {
        success: () => {
            hideModal("#edit_latex_packages_modal");
        },
        error: (error) => {
            console.log(error);
        },
    });
}
