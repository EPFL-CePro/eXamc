import type { AnnotationState, MarkerArea } from '@markerjs/markerjs3';
import type { PageData } from './api';

/** A page was loaded from the server, before its image is drawn. */
export interface PageLoadedDetail {
    copyNo: string;
    pageNo: string;
    data: PageData;
    /** Whether the page is part of the review group (a copy's other pages can be opened too). */
    inGroup: boolean;
}

const PAGE_LOADED = 'review:page-loaded';
const AREA_CREATED = 'review:area-created';
const AREA_SHOWN = 'review:area-shown';
const TOGGLE_PAGES_LIST = 'review:toggle-pages-list';
const MARKERS_SAVED = 'review:markers-saved';

export function emitPageLoaded(detail: PageLoadedDetail): void {
    document.dispatchEvent(new CustomEvent(PAGE_LOADED, {detail}));
}

export function onPageLoaded(listener: (detail: PageLoadedDetail) => void): void {
    document.addEventListener(PAGE_LOADED, (event) => listener((event as CustomEvent<PageLoadedDetail>).detail));
}

/** A MarkerArea was created for a page and added to the document (still hidden until its page is drawn). */
export function emitAreaCreated(area: MarkerArea): void {
    document.dispatchEvent(new CustomEvent(AREA_CREATED, {detail: area}));
}

export function onAreaCreated(listener: (area: MarkerArea) => void): void {
    document.addEventListener(AREA_CREATED, (event) => listener((event as CustomEvent<MarkerArea>).detail));
}

/** A MarkerArea is on screen with its page drawn (a new page, or the same page refitted). */
export function emitAreaShown(area: MarkerArea): void {
    document.dispatchEvent(new CustomEvent(AREA_SHOWN, {detail: area}));
}

export function onAreaShown(listener: (area: MarkerArea) => void): void {
    document.addEventListener(AREA_SHOWN, (event) => listener((event as CustomEvent<MarkerArea>).detail));
}

/**
 * Asks the pages list to collapse (true), expand (false) or switch (no argument).
 * Also works from outside the modules: document.dispatchEvent(new CustomEvent('review:toggle-pages-list', {detail: true})).
 */
export function emitTogglePagesList(collapse?: boolean): void {    
    document.dispatchEvent(new CustomEvent(TOGGLE_PAGES_LIST, {detail: collapse}));
}

export function onTogglePagesList(listener: (collapse?: boolean) => void): void {
    document.addEventListener(TOGGLE_PAGES_LIST, (event) => {
        const detail = (event as CustomEvent<unknown>).detail;        
        listener(typeof detail === 'boolean' ? detail : undefined);
    });
}

/** A page's markers were saved: as they were before (last saved) and as they are now. */
export interface MarkersSavedDetail {
    previous: AnnotationState;
    saved: AnnotationState;
}

export function emitMarkersSaved(detail: MarkersSavedDetail): void {
    document.dispatchEvent(new CustomEvent(MARKERS_SAVED, {detail}));
}

export function onMarkersSaved(listener: (detail: MarkersSavedDetail) => void): void {
    document.addEventListener(MARKERS_SAVED, (event) => listener((event as CustomEvent<MarkersSavedDetail>).detail));
}