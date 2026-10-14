import { parseJson, postText } from '@examc/helpers/http.ts';

import type { PagePosition, Zoom } from './types.ts';
import { ZoomsModal } from './zooms-modal.ts';

interface ZoomsConfig {
    zoomsUrl: string;
    updateZoneUrl: string;
    /** Called by the dialog's previous/next buttons. */
    onNavigate: (step: 1 | -1) => void;
}

let config: ZoomsConfig | null = null;

/** The dialog, while it's open. */
let modal: ZoomsModal | null = null;
let current: PagePosition | null = null;
/** Set once a zone was toggled: closing the dialog then reloads the page, so its summaries are up to date. */
let changed = false;
/** Incremented on every load, so responses for a page the user already left are ignored. */
let loadToken = 0;

/** Sets the endpoints and the navigation. Called by index.ts once the DOM has loaded. */
export function initZooms(zoomsConfig: ZoomsConfig): void {
    config = zoomsConfig;
}

/**
 * Opens the dialog on a page's box zooms (or switches to that page if it's already open).
 *
 * @param {PagePosition} position - The copy and page.
 */
export async function openZooms(position: PagePosition): Promise<void> {
    if (!config) return;
    current = position;

    if (!modal) {
        modal = new ZoomsModal({
            onNavigate: config.onNavigate,
            onHidden: () => {
                modal = null;
                if (changed) window.location.reload();
            },
        });
        modal.show();
    }
    modal.setPosition(position);

    await loadZooms();
}

async function loadZooms(): Promise<void> {
    if (!config || !current) return;
    const token = ++loadToken;
    const { copy, page } = current;

    try {
        const zooms = parseJson<Zoom[]>(await postText(config.zoomsUrl, { copy, page })) ?? [];
        // The dialog may have been closed, or moved to another page, while loading.
        if (token !== loadToken || !modal) return;
        modal.setZooms(
            zooms.filter((zoom) => !zoom.checked).map(zoomItem),
            zooms.filter((zoom) => zoom.checked).map(zoomItem),
        );
    } catch (error) {
        if (token === loadToken) console.error(error);
    }
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