import { Chart, type Plugin } from 'chart.js/auto';

import type { ByExamChart, McqChart as ClosedEndedChart, OpenChart } from './types.ts';
import { byId } from '@examc/helpers/dom.ts';

/** palette.js, loaded by base.html: `palette(scheme, count)` returns colors as hex without '#'. */
type Palette = (scheme: string, count: number) => string[];

/**
 * Colors of a palette.js scheme.
 *
 * @param {string} scheme - The scheme, e.g. 'mpn65'.
 * @param {number} count - The number of colors.
 * @return {string[]} The colors, as CSS hex colors.
 */
function paletteColors(scheme: string, count: number): string[] {
    const palette = (window as unknown as { palette?: Palette }).palette;
    return palette ? palette(scheme, count).map((hex) => `#${hex}`) : [];
}

/** Writes each bar's value, as a percentage, above it. */
const percentLabels: Plugin<'bar'> = {
    id: 'percentLabels',
    afterDatasetsDraw(chart) {
        const { ctx } = chart;
        ctx.save();
        ctx.font = `${Chart.defaults.font.size ?? 12}px ${Chart.defaults.font.family ?? 'sans-serif'}`;
        ctx.fillStyle = String(Chart.defaults.color);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';

        chart.data.datasets.forEach((dataset, datasetIndex) => {
            chart.getDatasetMeta(datasetIndex).data.forEach((bar, index) => {
                ctx.fillText(`${String(dataset.data[index])} %`, bar.x, bar.y - 5);
            });
        });
        ctx.restore();
    },
};


/**
 * Bar chart of a multiple-choice question's answers: share of students per answer,
 * with the number of students in the tooltip.
 *
 * @param {ClosedEndedChart} data - The question's answers.
 */
export function createClosedEndedChart({ canvasId, labels, rates, quantities }: ClosedEndedChart): void {
    const canvas = byId<HTMLCanvasElement>(canvasId);

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: 'Quantity',
                    data: rates,
                    backgroundColor: paletteColors('mpn65', labels.length) 
                }
            ]
        },
        options: {
            aspectRatio: 3,
            animation: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (item) => `${item.parsed.y} %`,
                        footer: (items) => `Qty : ${quantities[items[0]?.dataIndex ?? 0] ?? ''}`,
                    },
                },
            },
            scales: {
                x: { grid: { display: false } },
                y: { display: false, max: 120 }, // room for the labels above the bars
            },
        },
        plugins: [percentLabels],
    });
}

/**
 * Stacked horizontal bar of an open question's points: students per quarter of the max points,
 * from red (lowest quarter) to green.
 *
 * @param {OpenChart} data - The question's quarters.
 * @param {number} presentStudents - The number of students present (the bar's full length).
 */
export function createOpenChart({ canvasId, quarters }: OpenChart, presentStudents: number): void {
    const canvas = byId<HTMLCanvasElement>(canvasId);

    const colors = paletteColors('cb-RdYlGn', 4);
    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: [''],
            datasets: quarters.map((quarter, index) => ({
                label: `<= ${quarter.maxPoints} points`,
                data: [quarter.students],
                backgroundColor: colors[index] ?? '#999',
            })),
        },
        options: {
            indexAxis: 'y',
            aspectRatio: 3,
            plugins: { title: { display: true, text: 'Students Points' } },
            scales: {
                x: { stacked: true, max: presentStudents },
                y: { stacked: true },
            },
        },
    });
}

/**
 * Bar chart of a common question's answers in one of the common exams.
 *
 * @param {ByExamChart} data - The exam's answers to the question.
 */
export function createByExamChart({ canvasId, labels, percents }: ByExamChart): void {
    const canvas = byId<HTMLCanvasElement>(canvasId);

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { 
                    label: 'percent',
                    data: percents,
                    backgroundColor: paletteColors('mpn65', labels.length)
                }
            ],
        },
        options: {
            aspectRatio: 0.6, // narrow and tall, one per exam side by side
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: (item) => String(item.parsed.y) } },
            },
            scales: {
                x: { grid: { display: false } },
                y: { display: false, max: 100 },
            },
        },
    });
}