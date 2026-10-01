import { byId } from '@examc/helpers/dom.ts';
import { parseJson, postText } from '@examc/helpers/http.ts';

import type { PagePosition, Zoom } from './types.ts';
import {getModal} from "@examc/helpers/modals.ts";
import type { Modal } from 'bootstrap';

interface ZoomsConfig {
    zoomsUrl: string;
    updateZoneUrl: string;
    /** Called by the dialog's previous/next buttons. */
    onNavigate: (step: 1 | -1) => void;
}

let config: ZoomsConfig | null = null;
let elements: {
    dialog: HTMLElement;
    header: HTMLElement;
    unchecked: HTMLElement;
    checked: HTMLElement;
} | null = null;

let current: PagePosition | null = null;
/** Set once a zone was toggled: closing the dialog then reloads the page, so its summaries are up to date. */
let changed = false;
/** Incremented on every load, so responses for a page the user already left are ignored. */
let loadToken = 0;

let zoomDataCaptureDiagnosisDialogModal: Modal | null = null;

/** Wires the zooms dialog. */
export function initZooms(zoomsConfig: ZoomsConfig): void {
    config = zoomsConfig;

    elements = {
        dialog: byId('zoom-data-capture-diagnosis-dialog'),
        header: byId('zoom-data-capture-diagnosis-dialog-header'),
        unchecked: byId('zoom-unchecked-boxes'),
        checked: byId('zoom-checked-boxes'),
    };

    byId('zoomDataCapturePreviousBt').addEventListener('click', () => zoomsConfig.onNavigate(-1));
    byId('zoomDataCaptureNextBt').addEventListener('click', () => zoomsConfig.onNavigate(1));
    byId('zoom-dialog-close-btn').addEventListener('click', () => {
        if (changed) window.location.reload();
    });
}

/**
 * Opens the dialog on a page's box zooms (or switches to that page if it's already open).
 *
 * @param {PagePosition} position - The copy and page.
 */
export async function openZooms(position: PagePosition): Promise<void> {
    if (!elements) return;
    current = position;
    elements.header.replaceChildren('Boxes zooms for', document.createElement('br'), `Copy ${position.copy} / Page ${position.page}`);
    if (!zoomDataCaptureDiagnosisDialogModal) {
        zoomDataCaptureDiagnosisDialogModal = getModal({ type: "local", element: elements.dialog });
    }
    
    zoomDataCaptureDiagnosisDialogModal.show();

    await loadZooms();
}

async function loadZooms(): Promise<void> {
    if (!config || !current) return;
    const token = ++loadToken;
    const { copy, page } = current;

    try {
        const zooms = parseJson<Zoom[]>(await postText(config.zoomsUrl, { copy, page })) ?? [];
        if (token === loadToken) renderZooms(zooms);
    } catch (error) {
        if (token === loadToken) console.error(error);
    }
}

function renderZooms(zooms: Zoom[]): void {
    if (!elements) return;
    elements.unchecked.replaceChildren(...zooms.filter((z) => !z.checked).map(zoomItem));
    elements.checked.replaceChildren(...zooms.filter((z) => z.checked).map(zoomItem));
}

/** One zoom: the box image and its black value; clicking toggles the box. */
function zoomItem(zoom: Zoom): HTMLButtonElement {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'zoom-item';
    button.title = zoom.checked ? 'Checked: click to uncheck' : 'Unchecked: click to check';

    const image = new Image(40);
    image.src = `data:image/png;base64,${zoom.imagedata}`;
    image.alt = '';

    const value = document.createElement('span');
    value.textContent = zoom.bvalue.toFixed(3);

    button.append(image, value);
    button.addEventListener('click', () => void toggleZone(zoom));
    return button;
}

async function toggleZone(zoom: Zoom): Promise<void> {
    if (!config || !current) return;
    try {
        await postText(config.updateZoneUrl, {
            zoneid: String(zoom.zoneid),
            copy: current.copy,
            page: current.page,
        });
        changed = true;
        await loadZooms();
    } catch (error) {
        console.error(error);
    }
}
