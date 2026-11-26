import type { MarkerArea } from '@markerjs/markerjs3';
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
