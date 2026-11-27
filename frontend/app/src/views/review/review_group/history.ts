import type { AnnotationState } from '@markerjs/markerjs3';
import { byId, isTyping } from './dom';
import { onMarkersSaved, onPageLoaded } from './events';
import { isHighlight, onMarkerChange, restoreMarkers } from './markers';
import { state } from './state';
import { activateTool } from './tools';
import { currentArea } from './viewer/area';

/**
 * Undo / redo of the page's markers. Each page has its own history, which starts when it's opened.
 * The corrector box highlight isn't part of it: the grade decides it, so undo leaves it as it is.
 */

/** How many steps back can be undone. */
const LIMIT = 50;

/** The page's markers before each change (the last one first out), and the ones undone. */
const undoStack: AnnotationState[] = [];
const redoStack: AnnotationState[] = [];
/** Set while a step is saved: another one waits for it. */
let busy = false;

const undoButton = byId<HTMLButtonElement>('btn-undo');
const redoButton = byId<HTMLButtonElement>('btn-redo');

/** The markers a reviewer drew (the highlight aside), to compare two states. */
function drawn(markers: AnnotationState): string {
    return JSON.stringify(markers.markers.filter((marker) => !isHighlight(marker)));
}

function updateButtons(): void {
    undoButton.disabled = busy || undoStack.length === 0;
    redoButton.disabled = busy || redoStack.length === 0;
}

function clear(): void {
    undoStack.length = 0;
    redoStack.length = 0;
    updateButtons();
}

/** A save changed the drawn markers: the state it replaced can be undone to. */
function record(previous: AnnotationState, saved: AnnotationState): void {
    if (drawn(previous) === drawn(saved)) return;  // only the highlight changed
    undoStack.push(previous);
    if (undoStack.length > LIMIT) undoStack.shift();
    redoStack.length = 0;  // a new change: what was undone can't be redone anymore
    updateButtons();
}

/** Takes the last state of one stack, keeps the current one in the other, shows and saves it. */
async function step(from: AnnotationState[], to: AnnotationState[]): Promise<void> {
    if (busy || state.copyNo === null) return;
    busy = true;
    updateButtons();

    try {
        // A change still waiting for its save (the save is debounced) is recorded first
        await onMarkerChange();

        const target = from.pop();
        if (!target) return;

        const area = currentArea();
        const current = area.getState();
        to.push(current);

        // The drawn markers of then, with the highlight of now
        const next: AnnotationState = {
            ...target,
            markers: [...target.markers.filter((marker) => !isHighlight(marker)), ...current.markers.filter(isHighlight)],
        };
        state.markerState = next;
        restoreMarkers(next, area);
        await onMarkerChange({forceSave: true, allowHighlightOnly: true, allowEmpty: true, record: false});

        // Restoring stops a marker tool that was drawing: start it again
        activateTool(state.tool);
    } finally {
        busy = false;
        updateButtons();
    }
}

export function undo(): void {
    void step(undoStack, redoStack);
}

export function redo(): void {
    void step(redoStack, undoStack);
}

export function init(): void {
    undoButton.addEventListener('click', undo);
    redoButton.addEventListener('click', redo);

    onMarkersSaved(({previous, saved}) => record(previous, saved));
    onPageLoaded(clear);

    // Ctrl (Cmd on a Mac) + Z undoes, with Shift (or Ctrl + Y) redoes. Not while typing: a field,
    // or a text marker being written, has its own undo.
    document.addEventListener('keydown', (event) => {
        if (!(event.ctrlKey || event.metaKey) || event.altKey || isTyping(event)) return;
        if (document.querySelector('.modal.show')) return;

        const key = event.key.toLowerCase();
        if (key === 'z' && !event.shiftKey) undo();
        else if ((key === 'z' && event.shiftKey) || key === 'y') redo();
        else return;
        event.preventDefault();
    });

    updateButtons();
}