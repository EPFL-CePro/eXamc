import type { Api } from 'datatables.net-dt';

import { postForm } from '@examc/helpers/http.ts';
import { ConfirmModal } from '@examc/modals';

import type { PrepStudentRow } from "./prep-students-table.ts";
import { showFailure, showResult } from "./result.ts";

type AssignResponse = {
    updated?: number;
    first_seat?: string | null;
    last_seat?: string | null;
};

// Same rules as services/student/prep_seats.py: one run of "#" = the seat number with leading zeros
const NUMBER_PLACEHOLDER_RE = /#+/;

function formatSeat(pattern: string, number: number): string {
    return pattern.replace(NUMBER_PLACEHOLDER_RE, (run) => String(number).padStart(run.length, "0"));
}

function patternProblem(pattern: string): string | null {
    const runs = pattern.match(/#+/g)?.length ?? 0;
    if (runs === 0) return "The seats need a '#' for the seat number, e.g. R1-##.";
    if (runs > 1) return "The seats must have only one group of '#', e.g. R1-##.";
    return null;
}

/**
 * "Assign rooms and seats" form: gives a room and numbered seats to the students with an ID in a range,
 * with a preview of the result before sending it.
 */
export function initSeatsAssign(options: {
    form: HTMLFormElement;
    previewElement: HTMLElement;
    resultElement: HTMLElement;
    table: Api;
}): void {
    const { form, previewElement, resultElement, table } = options;
    const { assignUrl } = form.dataset;
    if (!assignUrl) {
        console.error("#assignSeatsForm missing data-assign-url attribute");
        return;
    }

    const input = (name: string) => form.elements.namedItem(name) as HTMLInputElement;
    const firstIdInput = input("first_id");
    const lastIdInput = input("last_id");
    const roomInput = input("room");
    const patternInput = input("seat_pattern");
    const firstNumberInput = input("first_number");
    const submitButton = form.querySelector<HTMLButtonElement>("button[type=submit]")!;
    const canSubmit = !submitButton.disabled;

    const rows = () => table.rows().data().toArray() as PrepStudentRow[];

    function readForm() {
        const firstId = Number.parseInt(firstIdInput.value, 10);
        const lastId = Number.parseInt(lastIdInput.value, 10);
        const firstNumber = Number.parseInt(firstNumberInput.value, 10);
        const room = roomInput.value.trim();
        const pattern = patternInput.value.trim();
        const students = rows()
            .filter((row) => row.copy_no >= firstId && row.copy_no <= lastId)
            .sort((a, b) => a.copy_no - b.copy_no);
        return { firstId, lastId, firstNumber, room, pattern, students };
    }

    // The problem preventing the assignment, or null
    function problem(values: ReturnType<typeof readForm>): string | null {
        const { firstId, lastId, firstNumber, room, pattern, students } = values;
        if (!Number.isInteger(firstId) || !Number.isInteger(lastId) || firstId < 1 || lastId < firstId) {
            return "Choose the IDs, from a first ID to a last ID that is not smaller.";
        }
        if (!room && !pattern) return "Give a room, seats, or both.";
        if (pattern) {
            const patternError = patternProblem(pattern);
            if (patternError) return patternError;
            if (!Number.isInteger(firstNumber) || firstNumber < 0) return "The first seat number must be 0 or more.";
        }
        if (!students.length) return `No student has an ID from ${firstId} to ${lastId}.`;
        return null;
    }

    function updatePreview(): void {
        const values = readForm();
        const error = problem(values);
        previewElement.classList.toggle("text-danger", error !== null);
        submitButton.disabled = !canSubmit || error !== null;
        if (error) {
            previewElement.textContent = error;
            return;
        }

        const { room, pattern, firstNumber, students } = values;
        const first = students[0];
        const last = students.at(-1);
        if (!first || !last) return;
        const parts = [];
        if (room) parts.push(`room ${room}`);
        if (pattern) {
            const lastNumber = firstNumber + students.length - 1;
            parts.push(students.length === 1
                ? `seat ${formatSeat(pattern, firstNumber)}`
                : `seats ${formatSeat(pattern, firstNumber)} to ${formatSeat(pattern, lastNumber)}`);
        }
        previewElement.textContent = `${students.length} student${students.length === 1 ? "" : "s"} `
            + `(ID ${first.copy_no} to ${last.copy_no}) will get ${parts.join(" and ")}.`;
    }

    // After each (re)load of the table: the range ends by default at the last student
    table.on("draw", () => {
        const ids = rows().map((row) => row.copy_no);
        const maxId = ids.length ? Math.max(...ids) : 1;
        lastIdInput.max = firstIdInput.max = String(maxId);
        const lastId = Number.parseInt(lastIdInput.value, 10);
        if (!Number.isInteger(lastId) || lastId > maxId) lastIdInput.value = String(maxId);
        updatePreview();
    });
    form.addEventListener("input", updatePreview);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const values = readForm();
        if (problem(values)) return;

        const { room, pattern, students, lastId } = values;
        const overwritten = students.filter((row) => (room && row.room) || (pattern && row.seat)).length;
        if (overwritten) {
            const what = [room && "room", pattern && "seat"].filter(Boolean).join(" or ");
            const confirmed = await ConfirmModal.confirm({
                title: "Replace rooms and seats",
                warning: `${overwritten} of these ${students.length} students already have a ${what}.`,
                message: "Replace them?",
                confirmLabel: "Yes, replace",
                confirmClass: "btn-danger",
            });
            if (!confirmed) return;
        }

        submitButton.disabled = true;
        try {
            const data = await (await postForm(assignUrl, {}, new FormData(form))).json() as AssignResponse;
            const seats = data.first_seat ? `, seats ${data.first_seat} to ${data.last_seat}` : "";
            showResult(resultElement, "success",
                `${data.updated} students updated${room ? `: room ${room}` : ""}${seats}.`);
            // Ready for the next room: it starts after this range
            firstIdInput.value = String(lastId + 1);
            lastIdInput.value = "";
            roomInput.value = "";
            table.ajax.reload();
        } catch (error) {
            showFailure(resultElement, error, "The rooms and seats were not assigned, nothing was changed:");
        } finally {
            updatePreview();
        }
    });
}
