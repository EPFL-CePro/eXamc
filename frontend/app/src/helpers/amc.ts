export interface AmcBox {
    stroke: string;
    strokeWidth: number;
    fill: string;
}


/** Highlight around an existing AMC box to significate a particular state (empty, invalid, etc.)*/
export interface AmcBoxFlag {
    stroke: string;
    strokeWidth: number;
    gap: number;
}



// ====================
// AMC boxes colors
// ====================
export function amcUncheckedBoxColor(opacity: number = 1): string {
    return `rgba(51, 163, 255, ${opacity})`;
}

export function amcCheckedBoxColor(opacity: number = 1): string {
    return `rgba(255, 0, 0, ${opacity})`;
}

export function amcErrorBoxColor(opacity: number = 1): string {
    return `rgb(255, 255, 51, ${opacity})`;
}

export function amcInvalidBoxFlagColor(opacity: number = 1): string {
    return `rgba(0, 255, 255, ${opacity})`;
}

export function amcEmptyBoxFlagColor(opacity: number = 1 ): string {
    return `rgb(255, 255, 31, ${opacity})`;
}


// ====================
// AMC box complete styling (stroke, color, fill, etc.)
// ====================

const boxOpacity = 0.75;

/** Color used by AMC that indicates a question's answer is wrong */
export const AMC_UNCHECKED_BOX: AmcBox = {
    stroke: amcUncheckedBoxColor(boxOpacity),
    strokeWidth: 5,
    fill: "transparent"
};

/** Color used by AMC that indicates a question is empty */
export const AMC_CHECKED_BOX: AmcBox = {
    stroke: amcCheckedBoxColor(boxOpacity),
    strokeWidth: 5,
    fill: "transparent"
};


export const AMC_ERROR_BOX: AmcBox = {
    stroke: amcErrorBoxColor(boxOpacity),
    strokeWidth: 5,
    fill: "transparent"
};


// ====================
// AMC box flag styling (stroke, stroke width, etc.)
// ====================

export const AMC_INVALID_BOX_FLAG: AmcBoxFlag = {
    stroke: amcInvalidBoxFlagColor(0.8),
    strokeWidth: 10,
    gap: 5
};


export const AMC_EMPTY_BOX_FLAG: AmcBoxFlag = {
    stroke: amcEmptyBoxFlagColor(0.8),
    strokeWidth: 10,
    gap: 5
};