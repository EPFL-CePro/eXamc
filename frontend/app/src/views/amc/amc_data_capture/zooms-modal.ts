import { ExamcModal } from '@examc/modals/base.ts';

import type { PagePosition } from './types.ts';

export interface ZoomsModalOptions {
    /** Called by the previous/next buttons. */
    onNavigate: (step: 1 | -1) => void;
    /** Called once the dialog is closed (and removed). */
    onHidden: () => void;
}

/** The box zooms of a page, unchecked and checked; built on the fly and removed once closed. */
export class ZoomsModal extends ExamcModal {
    private readonly unchecked: HTMLElement;
    private readonly checked: HTMLElement;

    public constructor({ onNavigate, onHidden }: ZoomsModalOptions) {
        super(ExamcModal.createElement({
            extraDialogClass: 'modal-xl',
            bodyContent: `
                <div class="modal-body">
                    <h6>Unchecked boxes</h6>
                    <div class="zoom-grid" data-unchecked></div>
                    <h6>Checked boxes</h6>
                    <div class="zoom-grid" data-checked></div>
                </div>
            `,
            footerContent: `
                <div class="me-auto">
                    <button type="button" class="btn btn-outline-secondary btn-sm" data-step="-1">
                        <i class="fa-solid fa-chevron-left" aria-hidden="true"></i><span> Previous page</span>
                    </button>
                    <button type="button" class="btn btn-outline-secondary btn-sm" data-step="1">
                        Next page <i class="fa-solid fa-chevron-right" aria-hidden="true"></i>
                    </button>
                </div>
                <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Close</button>
            `,
        }));

        this.unchecked = this.element.querySelector<HTMLElement>('[data-unchecked]')!;
        this.checked = this.element.querySelector<HTMLElement>('[data-checked]')!;

        // keys event listeners
        function handleArrowKeys(event: KeyboardEvent): void {
            if (event.key === 'ArrowLeft') {
                onNavigate(-1);
            } else if (event.key === 'ArrowRight') {
                onNavigate(1);
            }
        }

        document.addEventListener('keydown', handleArrowKeys);
        // button event listeners
        for (const button of this.element.querySelectorAll<HTMLButtonElement>('[data-step]')) {
            const step = button.dataset['step'] === '1' ? 1 : -1;
            button.addEventListener('click', () => onNavigate(step));
        }

        // cleanup
        this.element.addEventListener('hidden.bs.modal', () => {
            onHidden();
            document.removeEventListener('keydown', handleArrowKeys);
        });
    }

    /** Shows which page the zooms belong to. */
    public setPosition({ copy, page }: PagePosition): void {
        this.setTitle(`Boxes zooms: copy ${copy} / page ${page}`);
    }

    /**
     * Replaces the zooms.
     *
     * @param {Node[]} unchecked - The unchecked boxes.
     * @param {Node[]} checked - The checked boxes.
     */
    public setZooms(unchecked: Node[], checked: Node[]): void {
        this.unchecked.replaceChildren(...(unchecked.length ? unchecked : [ZoomsModal.emptyNotice()]));
        this.checked.replaceChildren(...(checked.length ? checked : [ZoomsModal.emptyNotice()]));
    }

    private static emptyNotice(): HTMLElement {
        const notice = document.createElement('span');
        notice.className = 'text-muted small';
        notice.textContent = 'None';
        return notice;
    }
}