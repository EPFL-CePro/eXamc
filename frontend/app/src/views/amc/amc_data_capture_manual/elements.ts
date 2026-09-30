import { byId, requireData } from '@examc/helpers/dom.ts';

export const root = byId('amc-data-capture');

export const urls = {
    scanUrl: requireData(root, 'scanUrl'),
    marks: requireData(root, 'marksUrl'),
    updateZone: requireData(root, 'updateZoneUrl'),
};

export const canvas = byId<HTMLCanvasElement>('canvasScan');
export const tableElement = byId<HTMLTableElement>('table-copies-pages');
export const typeButton = byId<HTMLButtonElement>('btnGroupDropType');
export const questionButton = byId<HTMLButtonElement>('btn-group-drop-questions');
export const prevButton = byId('capture-prev-btn');
export const nextButton = byId('capture-next-btn');
export const typeMenu = byId('capture-type-menu');
export const questionMenu = byId('capture-question-menu');