import { byId } from "@examc/helpers/dom.ts";
import { getText, parseJson, postText } from "@examc/helpers/http.ts";

import { URLS } from "./config.ts";
import { withQuery, withSpinner } from "./ajax.ts";
import { showSaveToast } from "./save-toast.ts";
import { LocalModal } from "@examc/modals/local.ts";

// Edit LaTeX file management

export async function openEditLaTeXFileDialog(type: string): Promise<void> {
    try {
        // The server answers [path, contents]
        const text = await withSpinner(true, () => getText(withQuery(URLS.editLatexFile, { type })));
        byId<HTMLTextAreaElement>("latex_source_text").value = parseJson<string[]>(text)?.[1] ?? "";
        byId("edit_latex_file_modal_title").innerText = "Edit " + type;
        byId("edit_latex_file_type").innerText = type;
        new LocalModal(byId("edit_latex_file_modal")).show();
    } catch (error) {
        console.error("[preparation] LaTeX request failed:", error);
        showSaveToast("Unable to load the LaTeX file.", true);
    }
}

export async function saveEditedLaTeXFile(): Promise<void> {
    const data = {
        source: byId<HTMLTextAreaElement>("latex_source_text").value,
        type: byId("edit_latex_file_type").innerText,
    };

    try {
        await withSpinner(true, () => postText(URLS.saveLatexFile, data));
        new LocalModal(byId("edit_latex_file_modal")).hide();
    } catch (error) {
        console.error("[preparation] LaTeX request failed:", error);
        showSaveToast("Not saved: the LaTeX file could not be saved.", true);
    }
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
    const container = byId("used_latex_packages_list");
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
    const container = byId("latex_package_search_results");
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
            byId<HTMLInputElement>("latex_package_search").value = "";
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
    renderPackageSearchResults(byId<HTMLInputElement>("latex_package_search").value);
}

function bindLatexPackageSearch(): void {
    const input = byId<HTMLInputElement>("latex_package_search");
    const results = byId("latex_package_search_results");

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

export async function openEditLaTeXPackagesDialog(type: string): Promise<void> {
    try {
        const text = await withSpinner(true, () => getText(withQuery(URLS.editLatexPackages, { type })));
        const data = parseJson<PackagesResponse>(text) ?? {};

        latexAvailablePackages = normalizeAvailablePackages(data.latex_available_packages);
        currentUsedPackages = normalizeUsedPackages(data.used_packages);

        bindLatexPackageSearch();
        renderUsedPackages();
        renderPackageSearchResults("");

        new LocalModal(byId("edit_latex_packages_modal")).show();

    } catch (error) {
        console.error("[preparation] LaTeX request failed:", error);
        showSaveToast("Unable to load the LaTeX packages.", true);
    }
}

export async function saveEditedLaTeXPackages(): Promise<void> {
    try {
        await withSpinner(true, () => postText(URLS.saveLatexPackages, { "new_used_packages[]": currentUsedPackages }));
        new LocalModal(byId("edit_latex_packages_modal")).hide();
    } catch (error) {
        console.error("[preparation] LaTeX request failed:", error);
        showSaveToast("Not saved: the LaTeX packages could not be saved.", true);
    }
}
