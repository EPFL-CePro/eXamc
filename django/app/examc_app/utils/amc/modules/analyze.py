import sys
import os
import re
import time
import shutil
import tempfile
from math import floor

from examc_app.utils.amc.modules.box import AMCBox
from examc_app.utils.amc.modules.calage import AMCCalage
from examc_app.utils.amc.modules.data import AMCData


# -------------------------------------------------------------------
# Stubs or placeholders for other AMC modules and functions
# -------------------------------------------------------------------

def debug(msg, *args):
    """Mimics debug from AMC::Basic."""
    print("[DEBUG]", msg, *args)

def debug_and_stderr(msg):
    """Mimics debug_and_stderr from AMC::Basic."""
    print("[DEBUG-ERR]", msg)

def translate_error(s, txt):
    """Mimics the Perl sub translate_error with error_text dictionary."""
    # Typically you'd handle localization. For now, a direct fallback:
    error_text = {
        'NMARKS':      "Not enough corner marks detected",
        'MAYBE_BLANK': "This page seems to be blank"
    }
    return error_text.get(s, txt)

def file_content(path):
    """Placeholder reading file content in binary."""
    with open(path, 'rb') as f:
        return f.read()

def magick_module(tool):
    """Placeholder returning the ImageMagick tool name."""
    # In real usage, might return path to `convert` or similar
    return tool

def clear_old(label, filepath):
    """Placeholder for removing old images if needed."""
    if os.path.exists(filepath):
        os.remove(filepath)

def get_debug():
    """Placeholder for get_debug(). Returns False by default."""
    return False

def studentids_string_filename(id0, id2):
    """Construct a filename component from student/page IDs."""
    return f"{id0}-{id2}"

def pageids_string(ids, path=False):
    """Mimic the Perl sub pageids_string(@spc)."""
    if path:
        return "-".join(str(x) for x in ids)
    else:
        return "/".join(str(x) for x in ids)

# Next, stubs for "AMC::Boite" or "AMC::Calage", etc.

# AMC::Queue stub
class AMCQueueStub:
    """Mimic AMC::Queue->new(...) and concurrency. We run tasks sequentially here."""

    def __init__(self, max_procs_label, n_procs, get_returned_values=False):
        self.tasks = []
        self.returned_values = get_returned_values
        self._results = []

    def add_process(self, func, *args):
        self.tasks.append((func, args))

    def run(self):
        for (f, a) in self.tasks:
            r = f(*a)
            if self.returned_values:
                self._results.append(r)
        self.tasks = []

    def returned_values(self):
        return self._results

    def killall(self):
        pass

# AMC::Subprocess stub
class AMCSubprocessStub:
    """Mimic AMC::Subprocess->new(...)."""

    def __init__(self, mode=None, args=None):
        self.mode = mode
        self.args = args or []

    def commande(self, cmd):
        """
        In Perl: $process->commande("load something"), returns an array of lines.
        Here, we return a mock list or parse 'cmd'.
        """
        debug(f"[Subprocess] command: {cmd}")
        # Return lines as if from actual process. For example:
        return []

    def ferme_commande(self):
        """Mimic $process->ferme_commande()"""
        pass

# AMC::Exec stub
class AMCExecStub:
    def __init__(self, name):
        self.name = name

    def signalise(self):
        pass

    def execute(self, tool, *args):
        debug(f"Executing: {tool} {' '.join(args)}")

# Now references to "capture" or "layout" modules from AMC::DataModule
# In real usage, your AMCData class loads them. We'll provide minimal placeholders:

class AMCCaptureStub:
    """Mimic capture DB interface."""
    def __init__(self):
        pass

    def begin_transaction(self, tag):
        debug(f"[capture] BEGIN TRANSACTION {tag}")

    def end_transaction(self, tag):
        debug(f"[capture] END TRANSACTION {tag}")

    def failed(self, sf):
        debug(f"[capture] Marking {sf} as failed")

    def new_page_copy(self, epc0, epc1, allocate):
        # Return a "copy number"
        return allocate if allocate else 1

    def set_page_auto(self, sf, *args):
        # Return True if data was overwritten
        return True

    def statement(self, name):
        """Return a stub statement object for 'deleteFailed' etc."""
        return AMCStatementStub()

    def set_layout_image(self, spc, layout_file):
        debug(f"[capture] set_layout_image => {layout_file}")

    def tag_overwritten(self, *args):
        debug("[capture] tag_overwritten called")

    def get_zoneid(self, spc, zone_type, question, answer, create):
        return 12345  # A stub zone ID

    def set_zone_auto_id(self, zoneid, val1, val2, nom_file, zoom_bin):
        debug(f"[capture] set_zone_auto_id => zoneid={zoneid}, {val1},{val2}, file={nom_file}")

class AMCStatementStub:
    def execute(self, *args):
        debug(f"[statement] execute => {args}")

class AMCLayoutStub:
    """Mimic layout DB interface."""
    def __init__(self):
        pass

    def begin_read_transaction(self, tag):
        debug(f"[layout] BEGIN READ {tag}")

    def end_transaction(self, tag):
        debug(f"[layout] END TRANSACTION {tag}")

    def dims(self, student, page):
        # Return (width, height, markdiameter, ???)
        return (210.0, 297.0, 5.0, None)

    def all_marks(self, student, page):
        return [10.0, 20.0, 30.0, 40.0]  # example coords

    def type_info(self, ttype, student, page):
        # Return list of dict like:
        # { numberid => 1, digitid => 1, xmin =>..., ymin=>..., flags =>... }
        if ttype == 'digit':
            return [{'numberid': 1, 'digitid': 1, 'xmin': 0, 'ymin': 0, 'xmax': 10, 'ymax': 5}]
        elif ttype == 'box':
            return [{'question': 1, 'answer':1, 'xmin': 20, 'ymin':20, 'xmax':25, 'ymax':25, 'flags':0}]
        elif ttype == 'namefield':
            return [{'xmin': 40, 'ymin':40, 'xmax':50, 'ymax':50}]
        return []

    def max_enter(self):
        return 2

    def variable(self, name):
        # e.g. "build:multi"
        return 0

    def pages_count(self):
        return 2

    def random_studentPage(self):
        # Return example student/page
        return (1234, 1)

    def exists(self, *epc):
        # Check if these epc exist
        return True

# Progress bar stub
class ProgressBarStub:
    def __init__(self, val, **kwargs):
        self.val = val

    def progres(self, delta):
        """Increment progress."""
        self.val += delta
        debug(f"Progress => {self.val}")

    def fin(self):
        debug("Progress finished")

# End stubs

# -------------------------------------------------------------------
# Global or default values (from the Perl script)
# -------------------------------------------------------------------
data_dir             = ""
cr_dir               = ""
debug_image_dir      = ""
debug_image          = ""
debug_pixels         = False
progress             = 0
progress_id          = 0
scans_list           = None
n_procs              = 0
project_dir          = ""
tol_mark             = ""
prop                 = 0.8
bw_threshold         = 0.6
blur                 = "1x1"
threshold            = "60%"
multiple             = False
ignore_red           = True
pre_allocate         = 0
try_three            = True
tag_overwritten      = True
unlink_on_global_err = False

# In Perl: the "queue" and "pid" are global
queue = None
pid   = None

# For shape flags, etc.:
BOX_FLAGS_SHAPE_OVAL = 2
BOX_FLAGS_DONTSCAN   = 4
ZONE_FRAME           = 101
ZONE_BOX             = 102
ZONE_DIGIT           = 103
ZONE_NAME            = 104
POSITION_BOX         = 201
POSITION_MEASURE     = 202

# Let's define some function placeholders used in the script

def error(e, process=None, scan=None, register_failed=None, silent=False):
    global debug_image, data_dir
    if process and debug_image:
        # process.commande(f"output {debug_image}")
        # process.ferme_commande()
        pass

    if silent:
        debug(e)
    else:
        debug(f"ERR: Scan {scan}: {e}")
        print(f"ERR: Scan {scan}: {e}")

    if register_failed:
        cap_data = AMCData(data_dir)  # from your amc_data import AMCData
        capture = cap_data.module('capture')
        capture.begin_transaction('CFLD')
        capture.failed(register_failed)
        capture.end_transaction('CFLD')

def check_rep(r, create=False):
    if create and r and not os.path.isdir(r):
        os.mkdir(r)
    if not os.path.isdir(r):
        raise RuntimeError(f"ERROR: directory does not exist: {r}")

# translate_error is defined above

def code_cb(nombre, chiffre):
    return f"{nombre}:{chiffre}"

def detecte_cb(k):
    m = re.match(r"^(\d+):(\d+)$", k)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None

def measure_box(process, ld, k, *spc):
    """
    Mimic measure_box from the script:
    - Possibly do a command: "id {spc0} {spc1} {q} {a}"
    - If not DONTSCAN, measure darkness data, etc.
    """
    r = 0
    flags = ld['flags'].get(k, 0)
    ld['corners.test'].setdefault(k, AMCBox())

    if spc:
        # If k=~^[0-9]+\.[0-9]+ => process->commande("id x y question answer")
        m = re.match(r'^(\d+)\.(\d+)$', k)
        if m:
            process.commande(f"id {spc[0]} {spc[1]} {m.group(1)} {m.group(2)}")
    else:
        if flags is None:
            flags = 0

    if not (flags & BOX_FLAGS_DONTSCAN):
        ld.setdefault('boxes.scan', {})
        ld['boxes.scan'][k] = AMCBox()
    else:
        ld.setdefault('boxes.scan', {})
        ld['boxes.scan'][k] = ld['boxes'][k].clone()
        ld['boxes.scan'][k].transforme(ld['transf'])

    # if not DONTSCAN, do measure:
    if not (flags & BOX_FLAGS_DONTSCAN):
        # create a command to measure
        # pc = ...
        # For now, a stub
        lines = process.commande("some measure command")
        for line in lines:
            # parse e.g. "TCORNER x,y", "COIN x,y", "PIX total filled", "ZOOM file"
            pass
        # set darkness data, e.g.  [ total, filled ]
        ld.setdefault('darkness.data', {})
        ld['darkness.data'][k] = [100, 50]  # e.g. 50 out of 100

    return r

def global_error(scans):
    global data_dir, unlink_on_global_err

    capture_data = AMCData(data_dir).module('capture')
    capture_data.begin_transaction('gFLD')
    for s in scans:
        if s.get('ids') is None:
            debug(f"Register unrecognized scan: {s['scan']}")
            capture_data.failed(s['scan'])
            s['registered'] = True
    capture_data.end_transaction('gFLD')

    if unlink_on_global_err:
        for s in scans:
            if not s.get('registered'):
                if os.path.isfile(s['scan']):
                    debug(f"Unlink scan: {s['scan']}")
                    # os.unlink(s['scan'])
                else:
                    debug(f"Scan to unlink not found: {s['scan']}")
    sys.exit(1)

def decimal(bits):
    r = 0
    for b in bits:
        r = 2*r + b
    return r

def get_binary_number(process, ld, i):
    ch = []
    a = 1
    fin = False
    while not fin:
        k = code_cb(i, a)
        if k in ld['boxes']:
            val = measure_box(process, ld, k)
            bit = 1 if val > 0.5 else 0
            ch.append(bit)
            a += 1
        else:
            fin = True
    return decimal(ch)

def get_id_from_boxes(process, ld, data_layout):
    epc = [
        get_binary_number(process, ld, 1),
        get_binary_number(process, ld, 2),
        get_binary_number(process, ld, 3)
    ]
    id_page = f"+{epc[0]}/{epc[1]}/{epc[2]}+"
    print(f"Page : {id_page}")
    debug(f"Found binary ID: {id_page}")

    data_layout.begin_read_transaction('cFLY')
    ok = True  # mimic => data_layout.exists(@epc)
    data_layout.end_transaction('cFLY')
    return (ok, epc[0], epc[1], epc[2])

# In Perl: sub marks_fit { ... } references AMC::Calage
cale = AMCCalage()

def command_transf(process, c, *args):
    """
    In Perl: parse the lines from process->commande(...)
    and store in c.
    """
    lines = process.commande(" ".join(args))
    for ln in lines:
        # e.g. parse "a=xx" or "MSE=xxx"
        pass

def marks_fit(process, ld, three=False):
    global cale
    cale = AMCCalage()
    # command_transf => "optim" + "3" if three => ld['frame'].draw_points()
    # We'll skip for brevity
    # Then ld['transf'] = cale
    ld['transf'] = {'some': 'transformation'}

def marks_fit_and_id(process, random_layout, data_layout, three=False):
    marks_fit(process, random_layout, three)
    ok, a, b, c = get_id_from_boxes(process, random_layout, data_layout)
    return (ok, [a, b, c])

# Get layout data from a random page
def get_layout_data(layout_obj, student, page, all_):
    """
    In Perl: returns a dictionary with boxes, flags, corners.test, etc.
    We'll produce a partial stub.
    """
    r = {
        'corners.test': {},
        'zoom.file': {},
        'darkness.data': {},
        'boxes': {},
        'flags': {}
    }
    # dims => (width, height, markdiameter, undef)
    r['width'], r['height'], r['markdiameter'], _ = layout_obj.dims(student, page)
    r['frame'] = AMCBox.new_complete(layout_obj.all_marks(student, page))
    # example for digit:
    for c in layout_obj.type_info('digit', student, page):
        k = code_cb(c['numberid'], c['digitid'])
        r['boxes'][k] = AMCBox.new_MN([c['xmin'], c['ymin'], c['xmax'], c['ymax']])
        r['flags'][k] = 0
    if all_:
        # gather box, namefield, etc.
        for c in layout_obj.type_info('box', student, page):
            k2 = f"{c['question']}.{c['answer']}"
            r['boxes'][k2] = AMCBox.new_MN([c['xmin'], c['ymin'], c['xmax'], c['ymax']])
            r['flags'][k2] = c['flags']
        for c in layout_obj.type_info('namefield', student, page):
            r['boxes']['namefield'] = AMCBox.new_MN([c['xmin'], c['ymin'], c['xmax'], c['ymax']])
    return r

def one_scan(scan, allocate, id_only):
    """
    The main function that processes a single scan,
    ported from sub one_scan { ... } in Perl.
    """
    global project_dir, debug_image_dir, debug_image
    global random_layout, try_three, bw_threshold, tol_mark_plus, tol_mark_moins
    global ignore_red, debug_pixels, multiple, pre_allocate, cr_dir, tag_overwritten
    global data_dir

    sf = scan
    if project_dir:
        # In Perl: abs2proj(...) => skip details here
        sf = sf

    sf_file = os.path.basename(sf)
    if debug_image_dir:
        debug_image_local = os.path.join(debug_image_dir, sf_file + ".png")
    else:
        debug_image_local = None

    debug(f"Analyzing scan {scan}")

    # Build our data and modules
    amc_data = AMCData(data_dir)
    layout = amc_data.module('layout')
    capture = amc_data.module('capture')

    # commands = AMC::Exec->new('AMC-analyse')
    commands = AMCExecStub("AMC-analyse")
    commands.signalise()

    # We create a process for marks detection
    process_args = [
        '-x', str(random_layout['width']),
        '-y', str(random_layout['height']),
        '-d', str(random_layout['markdiameter']),
        '-p', str(tol_mark_plus),
        '-m', str(tol_mark_moins),
        '-c', '3' if try_three else '4',
        '-t', str(bw_threshold),
        '-o', debug_image_local if debug_image_local else '1'
    ]
    if debug_image_local:
        process_args.append('-P')
    if ignore_red:
        process_args.append('-r')
    if debug_pixels:
        process_args.append('-k')

    process = AMCSubprocessStub(mode='detect', args=process_args)

    # e.g. lines = process.commande(f"load {scan}")
    lines = process.commande(f"load {scan}")
    coords = []
    warns = {}

    for l in lines:
        # parse e.g.: Frame[0]: x,y
        m_frame = re.match(r"Frame\[(\d+)\]:\s*(-?\d+\.?\d*)\s*[;,]\s*(-?\d+\.?\d*)", l)
        if m_frame:
            coords.append(float(m_frame.group(2)))
            coords.append(float(m_frame.group(3)))

        # parse e.g.: ! NMARKS
        m_warn = re.match(r"^\!\s*([A-Z_]+)", l)
        if m_warn:
            k = m_warn.group(1)
            # strip the leading "! "
            l2 = re.sub(r"^\!\s*", "", l)
            # replicate the s/// logic with a function:
            # s/^([A-Z_]+)(.*):\s([^\[]+)( \[.*\]|\.)$/
            pattern = r"^([A-Z_]+)(.*):\s([^\[]+)( \[.*\]|\.)$"
            def sub_warn(mo):
                ekey = mo.group(1)
                rest = mo.group(2)
                txt = mo.group(3)
                tail = mo.group(4)
                return f"[{ekey}{rest}] {translate_error(ekey, txt)}{tail}"
            l2 = re.sub(pattern, sub_warn, l2)
            warns[k] = l2

    # If not enough marks
    mayblank = warns.get('MAYBE_BLANK')
    nmarks = warns.get('NMARKS')
    m = mayblank or nmarks
    if m:
        if id_only:
            process.ferme_commande()
            return {
                'error': nmarks,
                'blank': True if mayblank else False
            }
        else:
            error(m, process=process, scan=scan, register_failed=sf if nmarks else '')
            return

    cadre_general = AMCBox.new_complete(coords)
    debug("Global frame:", cadre_general.txt())

    # ID detection
    epc, spc = [], []
    upside_down = False
    ok = False

    (ok, epc_res) = marks_fit_and_id(process, random_layout, layout)
    if try_three and not ok:
        (ok, epc_res) = marks_fit_and_id(process, random_layout, layout, True)

    if not ok:
        # rotate180
        process.commande("rotate180")
        (ok, epc_res) = marks_fit_and_id(process, random_layout, layout)
        if try_three and not ok:
            (ok, epc_res) = marks_fit_and_id(process, random_layout, layout, True)
        upside_down = True

    if not ok:
        # fail
        if id_only:
            process.ferme_commande()
            return {'error': 'No layout'}
        else:
            error(f"No layout for ID +{epc_res[0]}/{epc_res[1]}/{epc_res[2]}+",
                  process=process, scan=scan, register_failed=sf)
            return

    if ok and id_only:
        process.ferme_commande()
        return {'ids': [epc_res[0], epc_res[1]]}

    # command_transf => "rotateOK"
    command_transf(process, random_layout['transf'], "rotateOK")

    # get boxes from the "right" page
    layout.begin_read_transaction('cELY')
    ld = get_layout_data(layout, epc_res[0], epc_res[1], True)
    layout.end_transaction('cELY')

    # But keep all from random_layout
    for cat in ['boxes','boxes.scan','corners.test','darkness.data','zoom.file']:
        if cat not in ld:
            ld[cat] = {}
        for k, val in random_layout.get(cat, {}).items():
            if k not in ld[cat]:
                ld[cat][k] = val

    ld['transf'] = random_layout.get('transf', {})

    spc = [epc_res[0], epc_res[1]]
    if not debug_image_local:
        if multiple:
            capture.begin_transaction('cFCN')
            copy_num = capture.new_page_copy(epc_res[0], epc_res[1], allocate)
            spc.append(copy_num)
            if pre_allocate and allocate != copy_num:
                debug(f"WARNING: pre-allocation failed. {allocate} -> {pageids_string(spc)}")
            capture.set_page_auto(sf, *spc, -1, ld['transf'])
            capture.end_transaction('cFCN')
        else:
            spc.append(0)

    zoom_dir = tempfile.mkdtemp(dir=tempfile.gettempdir(), prefix="amc_")

    process.commande(f"zooms {zoom_dir}")

    # Read darkness data from all boxes
    for k in ld['boxes']:
        if re.match(r'^\d+\.\d+$', k):
            measure_box(process, ld, k, *spc)

    if debug_image_local:
        error("End of diagnostic", silent=True, process=process, scan=scan)
        return

    layout_file = f"page-{pageids_string(spc, path=True)}.jpg"
    if cr_dir:
        out_cadre = os.path.join(cr_dir, layout_file)
        process.commande(f"output {out_cadre}")

    if upside_down:
        print("Rotating...")
        commands.execute(magick_module("convert"), "-rotate", "180", scan, scan)

    nom_file = f"name-{studentids_string_filename(spc[0], spc[2])}.jpg" if len(spc) > 2 else "name-?.jpg"
    if 'namefield' in ld['boxes']:
        # "magick_perl_module()->new().Read($scan); Crop(...)"
        debug("Name box : ??? (stub)")

    capture.begin_transaction('CRSL')
    # annotate_source_change(capture) => stub
    overwritten = capture.set_page_auto(sf, spc[0], spc[1], spc[2], int(time.time()), ld['transf'])
    if overwritten:
        debug(f"Overwritten page data for [SCAN] {pageids_string(spc)}")
        if tag_overwritten:
            capture.tag_overwritten(*spc)
            print("VAR+: overwritten")

    stmt = capture.statement('deleteFailed')
    stmt.execute(sf)

    capture.set_layout_image(spc, layout_file)

    # attach cadre_general
    # cadre_general -> to_data( capture, get_zoneid(...), POSITION_BOX )
    zf = capture.get_zoneid(spc, ZONE_FRAME, 0, 0, True)
    cadre_general.to_data(capture, zf, POSITION_BOX)

    # For each box
    for k in ld['boxes']:
        zoneid = None
        m_box = re.match(r"^(\d+)\.(\d+)$", k)
        if m_box:
            question = int(m_box.group(1))
            answer   = int(m_box.group(2))
            zoneid = capture.get_zoneid(spc, ZONE_BOX, question, answer, True)
            if k in ld['corners.test']:
                ld['corners.test'][k].to_data(capture, zoneid, POSITION_MEASURE)
        else:
            cb = detecte_cb(k)
            if cb:
                zoneid = capture.get_zoneid(spc, ZONE_DIGIT, cb[0], cb[1], True)
            elif k == 'namefield':
                zoneid = capture.get_zoneid(spc, ZONE_NAME, 0, 0, True)
                capture.set_zone_auto_id(zoneid, -1, -1, nom_file, None)

        if zoneid:
            if k != 'namefield':
                flags_val = ld['flags'].get(k, 0)
                if flags_val & BOX_FLAGS_DONTSCAN:
                    debug(f"Box {k} is DONT_SCAN")
                    capture.set_zone_auto_id(zoneid, 1, 0, None, None)
                elif k in ld['darkness.data']:
                    dark_data = ld['darkness.data'][k]
                    zfile_data = None
                    if k in ld['zoom.file']:
                        zpath = os.path.join(zoom_dir, ld['zoom.file'][k])
                        zfile_data = file_content(zpath)
                    capture.set_zone_auto_id(zoneid, *dark_data, None, zfile_data)
                else:
                    debug(f"No darkness data for box {k}")

            if ld['boxes'].get(k) and not ld.get('boxes.scan', {}).get(k):
                ld.setdefault('boxes.scan', {})
                ld['boxes.scan'][k] = ld['boxes'][k].clone()
                ld['boxes.scan'][k].transforme(ld['transf'])
            if ld['boxes.scan'][k]:
                ld['boxes.scan'][k].to_data(capture, zoneid, POSITION_BOX)

    capture.end_transaction('CRSL')

    process.ferme_commande()
    shutil.rmtree(zoom_dir, ignore_errors=True)

    # Suppose we have a progress object
    # progress_h.progres(delta) => We'll do a no-op here
    return

def main():
    """
    Python version of the main logic at the end of the Perl script:
    - parse arguments
    - read scan list
    - do concurrency or not
    - handle multiple pages, etc.
    """
    global data_dir, cr_dir, debug_image_dir, debug_image, debug_pixels
    global progress, progress_id, scans_list, n_procs
    global project_dir, tol_mark, prop, bw_threshold, blur, threshold
    global multiple, ignore_red, pre_allocate, try_three, tag_overwritten
    global unlink_on_global_err

    # A minimal parse from sys.argv (for demonstration)
    scans = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg.startswith("--data="):
            data_dir = arg.split("=",1)[1]
        elif arg.startswith("--cr="):
            cr_dir = arg.split("=",1)[1]
        elif arg.startswith("--debug-image-dir="):
            debug_image_dir = arg.split("=",1)[1]
        elif arg.startswith("--liste-fichiers="):
            scans_list = arg.split("=",1)[1]
        elif arg.startswith("--project_dir="):
            project_dir = arg.split("=",1)[1]
        elif arg.startswith("--n_procs="):
            n_procs = int(arg.split("=",1)[1])
        elif arg.startswith("--bw-threshold="):
            bw_threshold = float(arg.split("=",1)[1])
        elif arg.startswith("--multiple"):
            multiple = True
        else:
            # treat as a scan file
            scans.append(arg)
        i += 1

    # read scans from scans_list if provided
    if scans_list and os.path.isfile(scans_list):
        with open(scans_list, "r", encoding="utf-8") as f:
            for line in f:
                line=line.strip()
                if os.path.isfile(line):
                    debug(f"Scan from list: {line}")
                    scans.append(line)
                else:
                    debug_and_stderr(f"WARNING. File does not exist: {line}")

    if not scans:
        sys.exit(0)

    # data_dir or cr_dir from project_dir if not defined
    if project_dir and not data_dir:
        data_dir = os.path.join(project_dir, "data")
    if project_dir and not cr_dir:
        cr_dir = os.path.join(project_dir, "cr")

    check_rep(data_dir, create=False)
    check_rep(cr_dir, create=True)

    # the progress bar
    progress_h = ProgressBarStub(progress, id=progress_id)
    delta = progress / (1 + len(scans)-1) if len(scans) > 1 else progress

    # In Perl, we create an AMCData and load layout, then check layout pages_count, etc.
    amc_data = AMCData(data_dir)
    layout = amc_data.module('layout')
    layout.begin_read_transaction('cRLY')
    max_enter = layout.max_enter()
    multi = layout.variable("build:multi")
    if layout.pages_count() == 0:
        layout.end_transaction('cRLY')
        error("No layout")
        sys.exit(1)
    debug(f"{layout.pages_count()} layouts")
    # random page
    ran = layout.random_studentPage()
    global random_layout
    random_layout = get_layout_data(layout, ran[0], ran[1], True)
    layout.end_transaction('cRLY')

    # concurrency stub
    global queue
    queue = AMCQueueStub('max.procs', n_procs)

    if max_enter > 1 and multiple and not multi:
        debug(f"Photocopy mode with {max_enter} answers pages")
        # first read ID from the scans (id_only=True)
        queue_id = AMCQueueStub('max.procs', n_procs, get_returned_values=True)
        for s in scans:
            queue_id.add_process(one_scan, s, 0, True)
        queue_id.run()
        scan_ids = queue_id.returned_values()

        # combine results with scans
        for i, scn in enumerate(scans):
            if scan_ids[i] is not None:
                scan_ids[i]['scan'] = scn
            else:
                # means error or blank
                scan_ids[i] = {'scan': scn}

        # remove blank
        recognized = []
        for r in scan_ids:
            if r.get('blank'):
                debug(f"Blank page: {r['scan']}")
                if unlink_on_global_err and os.path.isfile(r['scan']):
                    debug(f"Unlink scan: {r['scan']}")
                    # os.unlink(r['scan'])
            else:
                recognized.append(r)

        # unrecognized
        unrec = [x for x in recognized if 'ids' not in x]
        if unrec:
            debug("UNRECOGNIZED:")
            for u in unrec:
                debug(u['scan'])
            print(f"ERR: {len(unrec)} scans are not recognized:")
            # possibly we do: for i in range(min(5, len(unrec))):
            global_error(recognized)

        # The script checks grouping by student. We'll skip or do partial
        # ...
        # final pass
        queue2 = AMCQueueStub('max.procs', n_procs)
        for r in recognized:
            scn = r['scan']
            cpy = r.get('copy', 1)
            queue2.add_process(one_scan, scn, cpy, False)
        queue2.run()

    else:
        # simpler
        scan_i = 0
        for s in scans:
            a = pre_allocate + scan_i if pre_allocate else 0
            debug(f"Pre-allocate ID={a} for scan {s}")
            queue.add_process(one_scan, s, a, False)
            scan_i += 1
        queue.run()

    progress_h.fin()
    sys.exit(0)


if __name__ == "__main__":
    main()
