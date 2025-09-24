#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Translated from the original Perl script.
#
# Copyright (C) 2011-2022 Alexis Bienvenüe <paamc@passoire.fr>
#
# This file is part of Auto-Multiple-Choice
#
# Auto-Multiple-Choice is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 2 of
# the License, or (at your option) any later version.
#
# Auto-Multiple-Choice is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Auto-Multiple-Choice. If not, see
# <http://www.gnu.org/licenses/>.

import argparse
import os
import re
import sys
import time
from datetime import datetime

from examc_app.models import LayoutAssociation, LayoutQuestion, LayoutPage, LayoutMark, LayoutDigit, LayoutZone, LayoutBox, LayoutVariables


###############################################################################
# PLACEHOLDERS for AMC objects/functions used in the Perl code:
###############################################################################
# Instead of real AMC Perl modules, we just place placeholders here.
# In actual practice, you'd either replicate their logic in Python or
# call out to AMC’s Perl modules via subprocess or similar.
###############################################################################

# from AMC::Gui::Avancement
class AvancementPlaceholder:
    def __init__(self, progress=0, id_=""):
        self.progress = progress
        self.id_ = id_

    def progres(self, delta):
        # Move progress by delta
        self.progress += delta
        print(self.progress)

    def fin(self):
        # End progress
        pass

# Some enumerations used in the script:
BOX_ROLE_ANSWER         = 1
BOX_ROLE_QUESTIONONLY   = 2
BOX_ROLE_SCORE          = 3
BOX_ROLE_SCOREQUESTION  = 4
BOX_ROLE_QUESTIONTEXT   = 5
BOX_ROLE_ANSWERTEXT     = 6

BOX_FLAGS_SHAPE_OVAL    = 1 << 0
BOX_FLAGS_DONTSCAN      = 1 << 1
BOX_FLAGS_DONTANNOTATE  = 1 << 2
BOX_FLAGS_RETICK        = 1 << 3

ZONE_FLAGS_ID           = 1 << 0

###############################################################################

def debug(msg):
    # In Perl code, this might be something that prints debug messages
    # if some debug flag is set. For simplicity, just print here.
    # You can remove or replace with logging as you need.
    # print(f"[DEBUG] {msg}")
    pass

def show_utf8(txt):
    # In the Perl code, used to ensure printing in UTF-8 properly.
    # Here, just return the string unchanged or encode as needed.
    return txt

U_IN_ONE_INCH = {
    'in': 1.0,
    'cm': 2.54,
    'mm': 25.4,
    'pt': 72.27,
    'sp': 72.27 * 65536,
}

def read_inches_new(dim):
    """
        Convert a dimension string (e.g. '4cm', '10.5mm', '1.25in') to inches.
        Ignores leading/trailing whitespace. Raises ValueError if format is invalid.
        """
    dim = dim.strip()
    if not dim:
        raise ValueError(f"Empty dimension string")

    # Find where the unit part begins by scanning from the end for letters
    idx = len(dim)
    while idx > 0 and dim[idx - 1].isalpha():
        idx -= 1

    if idx == 0:
        raise ValueError(f"No numeric portion found in '{dim}'")

    # Separate the numeric part and the unit
    val_str = dim[:idx].strip()  # everything up to the start of letters
    unit = dim[idx:].strip()  # the trailing alphabetic part

    # Convert the numeric string to float
    try:
        val = float(val_str)
    except ValueError:
        raise ValueError(f"Invalid numeric portion in '{dim}'")

    # Lookup the unit in our dictionary
    conv = U_IN_ONE_INCH.get(unit)
    if conv is None:
        raise ValueError(f"Unknown unit '{unit}' in '{dim}'")

    # Convert to inches
    return val / conv

def read_inches(dim):
    """
    Convert dimension string (like '4cm', '10.5mm', etc.) to a float in "inches".
    """
    u_in_one_inch = {
        'in': 1.0,
        'cm': 2.54,
        'mm': 25.4,
        'pt': 72.27,
        'sp': 72.27 * 65536,
    }
    match = re.match(r'^\s*([+-]?\d*\.?\d*)\s*([a-zA-Z]+)\s*$', dim)
    if match:
        val, unit = match.groups()
        val = float(val)
        if unit in u_in_one_inch:
            return val / u_in_one_inch[unit]
        else:
            raise ValueError(f"Unknown unit: {unit} ({dim})")
    else:
        raise ValueError(f"Unknown dimension format: {dim}")

def add_case(arr, val):
    """
    In the Perl code, `ajoute` adjusts the bounding box array's min/max.
    - arr is [min, max]
    - val is new measurement
    """
    if val is None:
        return
    if len(arr) == 0:
        arr.extend([val, val])
    else:
        if val < arr[0]:
            arr[0] = val
        if val > arr[1]:
            arr[1] = val

def bbox(c):
    """
    c has c['bx'] = [min_x, max_x], c['by'] = [min_y, max_y].
    Return (min_x, max_x, max_y, min_y) like the Perl code does.
    That ordering is: left, right, top, bottom.
    """
    return (c['bx'][0], c['bx'][1], c['by'][1], c['by'][0])

def center(c, xy):
    """
    Returns center of c['bx'] or c['by'] as ( (min+max) / 2 ).
    """
    return (c[xy][0] + c[xy][1]) / 2.0

def is_digits_and_dots(s: str) -> bool:
    return all(ch.isdigit() or ch == '.' for ch in s)

def detect_layout():
    src = "/home/ludo/CEPRO/DEV_TESTS/AMC/testing/amc_project/EXAM-calage.xy"
    data_dir = "/home/ludo/CEPRO/DEV_TESTS/AMC/testing/amc_project/data"
    progress_id = ""
    progress = 0
    dpi = 300

    if not os.path.isfile(src):
        sys.exit(f"No src file {src}")
    if not os.path.isdir(data_dir):
        sys.exit(f"No data dir {data_dir}")

    # Simulate the AMC progress object
    avance = AvancementPlaceholder(progress, progress_id)

    # Simulate loading the AMC::Data
    # data = DataPlaceholder(data_dir)
    # layout = data.module('layout')
    # capture = data.module('capture')

    timestamp = int(time.time())

    # association code_in_amc_file => BOX_ROLE_*
    role = {
        'case':          BOX_ROLE_ANSWER,
        'casequestion':  BOX_ROLE_QUESTIONONLY,
        'score':         BOX_ROLE_SCORE,
        'scorequestion': BOX_ROLE_SCOREQUESTION,
        'qtext':         BOX_ROLE_QUESTIONTEXT,
        'atext':         BOX_ROLE_ANSWERTEXT,
    }

    flag_num = {
        'id': ZONE_FLAGS_ID,
    }

    # We'll hold our extracted data in these arrays/dicts
    pages = []
    flags = []
    pre_assoc = []
    page_number = 0
    build_vars = {}
    question_name = {}

    # We need a helper function for the flag logic
    def add_flag(identifier, flag):
        """
        Replicates the behavior in the Perl sub add_flag.
        If line is \dontscan{X}, we parse X => (student, question) in "S,Q" form
        and add the flag to the last flags entry if it matches, or create new.
        """
        match_sq = re.match(r'^(\d+),(\d+)$', identifier)
        if match_sq:
            student_str, question_str = match_sq.groups()
            student = int(student_str)
            question = int(question_str)
            if len(flags) > 0:
                lf = flags[-1]
                if lf['student'] == student and lf['question'] == question:
                    lf['flags'] |= flag
                    return
            flags.append({
                'student': student,
                'question': question,
                'flags': flag
            })
        else:
            debug(f"ERROR: flag which question? <{identifier}>")

    debug(f"Reading {src}...")

    # Each page has a dictionary:
    # {
    #   '-id': 'some string',
    #   '-p': page_number,
    #   '-dim_x': float_in_inch,
    #   '-dim_y': float_in_inch,
    #   '-page_x': float_in_inch,
    #   '-page_y': float_in_inch,
    #   '-cases': {...}
    # }
    # and each case is c['bx'] = [min_x, max_x], c['by'] = [min_y, max_y], etc.

    #define pattern searches
    match_page_pattern = re.compile(r'\\page\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}(?:\{([^}]+)\}\{([^}]+)\})?')
    match_tracepos_pattern = re.compile(r'\\tracepos\{(.+?)\}\{([+-]?\d+\.?\d*[a-zA-Z]+)\}\{([+-]?\d+\.?\d*[a-zA-Z]+)\}(?:\{([a-zA-Z]*)\})?')
    match_boxchar_pattern = re.compile(r'\\boxchar\{([^}]+)\}\{(.*)\}$')
    match_dontscan_pattern = re.compile(r'\\dontscan\{([^}]+)\}')
    match_dontannotate_pattern = re.compile(r'\\dontannotate\{([^}]+)\}')
    match_retick_pattern = re.compile(r'\\retick\{([^}]+)\}')
    match_assoc_pattern = re.compile(r'\\association\{(\d+)\}\{([^}]+)\}\{([^}]+)\}')
    match_with_pattern = re.compile(r'\\with\{([^}=]+)=(.*)\}')
    match_qn_pattern = re.compile(r'\\question\{(\d+)\}\{(.*)\}')


    current_cases = None

    dt = datetime.now()
    with (open(src, 'r', encoding='utf-8') as fh):
        for line in fh:
            line = line.rstrip('\n')
            # # 1) \page{ID}{dx}{dy}{px}{py}...
            if line.startswith('\\page{'):

                # get values
                page_id, dx, dy, px, py = line[6:-1].split('}{')

                # Instead of "not px or numeric_re.match(px)", use either compiled regex OR a quick check:
                if not px or is_digits_and_dots(px):
                    px = dx
                if not py or is_digits_and_dots(py):
                    py = dy

                page_number += 1
                current_cases={}
                pages.append({
                    '-id': page_id,
                    '-p': page_number,
                    '-dim_x': read_inches_new(dx),
                    '-dim_y': read_inches_new(dy),
                    '-page_x': read_inches_new(px),
                    '-page_y': read_inches_new(py),
                    '-cases': {}
                })

            # 2) \tracepos{...}{...}{...}{optional shape?}
            if line.startswith('\\tracepos{'):
                # get values
                i, x_str, y_str, shape = line[10:-1].split('}{')
                # Remove any leading "NN/NN:" from i
                i = i.split(':')[1]

                x = read_inches_new(x_str)
                y = read_inches_new(y_str)

                case = current_cases.get(i)
                if case is None:
                    current_cases[i] = {
                        'bx': [],
                        'by': [],
                        'flags': 0,
                        'shape': '',
                        'char': None
                    }
                add_case(current_cases[i]['bx'], x)
                add_case(current_cases[i]['by'], y)

                if shape and shape != '':
                    if current_cases[i]['shape'] and current_cases[i]['shape'] != shape:
                        debug(f"WARNING: different shapes for a single box ({i})")
                    else:
                        current_cases[i]['shape'] = shape
                        if shape == 'oval':
                            current_cases[i]['flags'] |= BOX_FLAGS_SHAPE_OVAL

            # 3) \boxchar{...}{...}
            if line.startswith('\\boxchar{'):
                # get values
                i, char = line[9:-1].split('}{')
                i = i.split(':')[1]
                case = current_cases.get(i)
                if case is None:
                    current_cases[i] = {
                        'bx': [],
                        'by': [],
                        'flags': 0,
                        'shape': '',
                        'char': None
                    }
                current_cases[i]['char'] = char

            # 4) \dontscan{X}, \dontannotate{X}, \retick{X}
            if line.startswith('\\dontscan{'):
                value = line[10:-1].split(',')[1]
                add_flag(value, BOX_FLAGS_DONTSCAN)

            if line.startswith('\\dontannotate{'):
                value = line[14:-1].split(',')[1]
                add_flag(value, BOX_FLAGS_DONTANNOTATE)

            if line.startswith('\\retick{'):
                value = line[8:-1].split(',')[1]
                add_flag(value, BOX_FLAGS_RETICK)

            # # 5) \association{STUDENT}{ID}{FILENAME}
            # if line.startswith('\\association{'):
            #     match_assoc = match_assoc_pattern.search(line)
            #     if match_assoc:
            #         student_str, assoc_id, filename = match_assoc.groups()
            #         filename = re.sub(r'[\{\}\\]+', '', filename)  # remove braces or backslashes
            #         student_int = int(student_str)
            #         pre_assoc.append([student_int, assoc_id, filename])
            #
            # if line.startswith('\\with{'):
            # # 6) \with{key=value}
            #     match_with = match_with_pattern.search(line)
            #     if match_with:
            #         key, val = match_with.groups()
            #         build_vars[key] = val
            #
            # if line.startswith('\\question{'):
            # # 7) \question{QUESTION_ID}{some text}
            #     match_qn = match_qn_pattern.search(line)
            #     if match_qn:
            #         qid_str, txt = match_qn.groups()
            #         question_name[qid_str] = txt

    # Done reading SRC

    # Prepare storing to the "database" (placeholder)
    # layout.begin_transaction('MeTe')
    # layout.clear_mep()
    # layout.clear_variables('build:%')


    spenttime = datetime.now() - dt
    print(spenttime.total_seconds())


    for k, v in build_vars.items():
        debug(f"build:{k}={show_utf8(v)}")
        LayoutVariables.objects.update_or_create(name = "build:" + k, value = v)

    # This replicates: annotate_source_change($capture);
    # in the original script. We'll just place a placeholder here.
    # If needed, you'd call some method in your real implementation.
    # capture.annotate_source_change(...) ???

    # Pre-association
    debug("Pre-association...")
    for pa in pre_assoc:
        student, assoc_id, filename = pa
        LayoutAssociation.objects.update_or_create(student = student, association_id = assoc_id, filename = filename)
        #layout.new_association(student, assoc_id, filename)

    # question_name additions
    debug("Applying question names to DB ...")
    for qid, val in question_name.items():
        if val != '':
            LayoutQuestion.objects.create(question = qid, name = val)
            #layout.question_name(qid, val)

    # Now loop over each page in pages and create the layout
    # The original code calls: get_epc($p->{-id}), get_ep ...
    # We'll just store placeholders (since AMC uses an internal DB).

    debug("Writing to database ...")
    delta = (1.0 / len(pages)) if len(pages) > 0 else 0

    for p in pages:
        # compute the average diameter for the 4 corner marks if present
        diameter_marque_sum = 0.0
        dmn = 0

        # For each traced position in p['-cases']:
        for k, c_val in p['-cases'].items():
            # Multiply all bounding box coords by DPI,
            # and also invert the Y (since the original code does:
            #   p->{-page_y} - coordinate
            #   Then multiply by DPI
            for idx in (0, 1):
                c_val['bx'][idx] *= dpi
                c_val['by'][idx] = dpi * (p['-page_y'] - c_val['by'][idx])

            # If the key matches position[HB][GD], use it to measure corner marks
            if re.search(r'position[HB][GD]$', k):
                # The "width" in x or y is difference of c_val['bx'][1] - c_val['bx'][0], etc.
                dx = abs(c_val['bx'][1] - c_val['bx'][0])
                dy = abs(c_val['by'][1] - c_val['by'][0])
                diameter_marque_sum += (dx + dy)
                dmn += 2

        diameter_marque = diameter_marque_sum / dmn if dmn else 0.0

        # get exam/page code from p['-id']
        epc = p['-id'].split('/')
        ep = epc[0:2]  # the original code uses @epc[0,1] for some queries

        # In the Perl script:
        #   $layout->statement('NEWLayout')->execute(@epc, p_number, dpi, width_px, height_px, diameter, source_id)
        LayoutPage.objects.update_or_create(student = epc[0], page = epc[1], checksum = epc[2], subjectpage = p['-p'], dpi = dpi,
                       width = dpi * p['-dim_x'],
                       height = dpi * p['-dim_y'],
                       markdiameter = diameter_marque)

        # layout.statement('NEWLayout') \
        #       .execute(epc[0], epc[1], epc[2], epc[3],
        #                p['-p'], dpi,
        #                dpi * p['-dim_x'],
        #                dpi * p['-dim_y'],
        #                diameter_marque,
        #                source_id)

        if not dmn:
            # If there's no corner marks, skip the rest for this page
            avance.progres(delta)
            continue

        ccases = p['-cases']

        # We expect 4 corners: positionHG, positionHD, positionBD, positionBG
        for corner in ['positionHG','positionHD','positionBD','positionBG']:
            if corner not in ccases:
                raise ValueError(f"Needs {corner} from page {p['-id']}")

        # Insert the 4 marks
        nc = 0
        for pos in ['positionHG','positionHD','positionBD','positionBG']:
            nc += 1
            LayoutMark.objects.update_or_create(student=ep[0],page=ep[1],corner=nc,x=center(ccases[pos], 'bx'),y=center(ccases[pos], 'by'))

        # Now handle all the remaining boxes
        for k, c_val in sorted(ccases.items()):
            # \digit =>  \chiffre:STUDENT,INDEX
            digit_match = re.match(r'chiffre:(\d+),(\d+)$', k)
            if digit_match:
                stud, idx = digit_match.groups()
                LayoutDigit.objects.update_or_create(
                    student = ep[0], page = ep[1],
                    numberid = int(stud), digitid = int(idx), xmin = c_val['bx'][0], xmax = c_val['bx'][1], ymin = c_val['by'][0], ymax = c_val['by'][1])

            # \zone =>  __zone:FLAGS,ZONE_NAME
            zone_match = re.match(r'__zone:([^:]+):([^:]+)', k)
            if zone_match:
                flags_str, zone = zone_match.groups()
                flags_ = 0
                for f in re.split(r'\s*,\s*', flags_str):
                    if f in flag_num:
                        flags_ |= flag_num[f]
                    else:
                        debug(f"Unknown zone flag: {f}")
                LayoutZone.objects.update_or_create(
                    student = ep[0], page = ep[1],
                    zone = zone, flags = flags_ ,xmin = c_val['bx'][0], xmax = c_val['bx'][1], ymin = c_val['by'][0], ymax = c_val['by'][1])

            # \case =>  (case|casequestion|score|scorequestion|qtext|atext):(NAME):(Q),(A)
            box_match = re.match(
                r'(case|casequestion|score|scorequestion|qtext|atext):([^:]+):(\d+),(-?\d+)$',
                k
            )
            if box_match:
                typ, name, q_str, a_str = box_match.groups()
                q_int = int(q_str)
                a_int = int(a_str)
                debug(f"- Box {k}")
                r_ = role.get(typ, BOX_ROLE_ANSWER)
                LayoutBox.objects.update_or_create(
                    student = ep[0], page = ep[1],
                    role = r_,
                    question = q_int,
                    answer = a_int,
                    xmin = c_val['bx'][0], xmax = c_val['bx'][1], ymin = c_val['by'][0], ymax = c_val['by'][1],
                    flags = c_val['flags'],
                    char = c_val.get('char', None)
                )

        avance.progres(delta)

    # Finally, handle the question flags
    debug("Flagging questions...")
    for f_ in flags:
        LayoutBox.objects.update_or_create(student=f_['student'],question=f_['question'],role=BOX_ROLE_ANSWER,flags=f_['flags'])

    # End progress
    avance.fin()

