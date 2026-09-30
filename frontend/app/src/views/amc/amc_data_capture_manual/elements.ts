import { byId, requireData } from '@examc/helpers/dom.ts';

export const root = byId('amc-data-capture');

export const urls = {
    scanUrl: requireData(root, 'scanUrl'),
    marks: requireData(root, 'marksUrl'),
    updateZone: requireData(root, 'updateZoneUrl'),
};

export const canvas = byId<HTMLCanvasElement>('canvas-scan');
export const tableElement = byId<HTMLTableElement>('table-copies-pages');