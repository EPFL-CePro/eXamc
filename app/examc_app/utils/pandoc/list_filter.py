#!/usr/bin/env python3
import sys

import pandocfilters as pf


def custom_filter(key, value, format, meta):
    print("key:"+str(key),file=sys.stderr)
    if key == 'OrderedList':
        latex_itemize = set_ordered_list(key,value,format,meta)

        return latex_itemize


def set_ordered_list(key, value, format, meta):
    # Start the LaTeX itemize list
    items = [pf.RawBlock('latex', '\\begin{itemize}')]
    print("item:", value, file=sys.stderr)
    for item in value:
        print("item:",item, file=sys.stderr)
        if type(item) == 'list':
            list = set_ordered_list(key, item, format, meta)
            items.append(pf.RawBlock('latex', list))
        items.append(pf.RawBlock('latex', '\\item' + item))

    # End the LaTeX itemize list
    items.append(pf.RawBlock('latex', '\\end{itemize}'))


if __name__ == "__main__":
    pf.toJSONFilter(custom_filter)