#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import math
import subprocess
import tempfile
import shutil
import re
from pathlib import Path
from datetime import datetime

# -------------------------------------------------------------------------
# Global constants and placeholders
# -------------------------------------------------------------------------
COMBO_ID = 1
COMBO_TEXT = 0

amc_base_path = None
if "AMCBASEDIR" in os.environ:
    amc_base_path = os.environ["AMCBASEDIR"]
else:
    # This logic replicates the strip logic from:
    #     __FILE__ =~ s|/Basic\.pm$||;
    #     ... s|/AMC$||; s|/perl$||;
    # In Python, if you have a known file path, you'd do something like:
    # amc_base_path = os.path.dirname(os.path.abspath(__file__))
    # then remove trailing parts as needed. We'll keep it simple:
    this_file = os.path.abspath(__file__)
    # For demonstration, replicate the "strip" approach:
    # This is purely illustrative:
    temp_path = re.sub(r'/Basic\.pm$', '', this_file)
    temp_path = re.sub(r'/AMC$', '', temp_path)
    temp_path = re.sub(r'/perl$', '', temp_path)
    amc_base_path = temp_path

# -------------------------------------------------------------------------
# This dictionary replicates the Perl %install_dirs
# -------------------------------------------------------------------------
install_dirs = {
    'lib'       : "/usr/lib/AMC",
    'libexec'   : "/usr/lib/AMC/exec",
    'libperl'   : "/usr/lib/AMC/perl",
    'icons'     : "/usr/share/auto-multiple-choice/icons",
    'models'    : "/usr/share/auto-multiple-choice/models",
    'doc/auto-multiple-choice': "/usr/share/doc/auto-multiple-choice",
    'locale'    : "/usr/share/locale",
}

# Simple placeholders for some debug logic
_amc_debug = False
_amc_debug_filename = ''
_amc_debug_filehandle = None
_debug_memory = []

def debug_raw(*msgs):
    """
    Write debug messages directly, without timestamps.
    Equivalent to 'debug_raw' in AMC::Basic.
    """
    global _amc_debug, _amc_debug_filename, _amc_debug_filehandle
    if not _amc_debug:
        return
    for msg in msgs:
        if not msg.endswith('\n'):
            msg += '\n'
        if _amc_debug_filename in ('stderr', 'stdout'):
            _amc_debug_filehandle.write(msg)
            _amc_debug_filehandle.flush()
        else:
            # For a file, we can do a lock or something similar.
            _amc_debug_filehandle.write(msg)
            _amc_debug_filehandle.flush()

def debug(*msgs):
    """
    Write debug messages with timestamps. Equivalent to 'debug' in AMC::Basic.
    """
    global _amc_debug
    if not _amc_debug:
        return
    t = sum(os.times()[:4])  # user+sys times
    for msg in msgs:
        line = f"[{os.getpid():7d},{t:7.02f}] {msg}"
        debug_raw(line)

def debug_and_stderr(*msgs):
    """
    Equivalent to 'debug_and_stderr'. Write to debug and also to stderr (unless debugging is itself stderr).
    """
    global _amc_debug, _amc_debug_filename
    debug(*msgs)
    if not (_amc_debug and _amc_debug_filename == 'stderr'):
        for m in msgs:
            sys.stderr.write(m + "\n")

def debug_file():
    """
    Return the current debug filename. Equivalent to 'debug_file' in Perl.
    """
    global _amc_debug, _amc_debug_filename
    return _amc_debug_filename if _amc_debug else ''

def next_debug(*msgs):
    """
    Buffers debug messages if debug isn't yet turned on.
    """
    global _amc_debug, _debug_memory
    if _amc_debug:
        debug(*msgs)
    else:
        _debug_memory.extend(msgs)

def set_debug(debug_val):
    """
    Equivalent to 'set_debug' in the Perl code.
    """
    global _amc_debug, _amc_debug_filename, _amc_debug_filehandle, _debug_memory

    # flush or restore? We don't replicate the "STDERR backup" exactly
    if debug_val:
        empty = False
        if debug_val.lower() in ('1', 'yes'):
            # Continue with existing file or create new
            debug_val = _amc_debug_filename or 'new'

        if debug_val == 'stderr':
            _amc_debug_filehandle = sys.stderr
            _amc_debug_filename   = 'stderr'
        elif debug_val == 'stdout':
            _amc_debug_filehandle = sys.stdout
            _amc_debug_filename   = 'stdout'
        else:
            # Use a file
            if debug_val.lower() == 'new':
                empty = True
                # create new
                tmp = tempfile.NamedTemporaryFile(prefix='AMC-DEBUG-', suffix='.log', delete=False)
                _amc_debug_filehandle = open(tmp.name, 'a', encoding='utf-8')
                _amc_debug_filename   = tmp.name
            else:
                # open the file in append mode
                empty = not os.path.exists(debug_val) or os.path.getsize(debug_val) == 0
                _amc_debug_filehandle = open(debug_val, 'a', encoding='utf-8')
                _amc_debug_filename = debug_val

        _amc_debug = True
        debug("[{}]>>".format(os.getpid()))
        if empty:
            debug_general_info()

        # flush memory
        for m in _debug_memory:
            debug(m)
        _debug_memory = []

        debug(f"{sys.argv[0]} enters debugging mode.")
    else:
        # leaving debug mode
        if _amc_debug_filehandle and _amc_debug_filehandle not in (sys.stderr, sys.stdout):
            _amc_debug_filehandle.close()
        _amc_debug = False

def get_debug():
    return _amc_debug

def debug_general_info():
    """
    Writes basic environment information to the debug file, like version data, etc.
    """
    global _amc_debug, _amc_debug_filehandle
    if not _amc_debug:
        return

    _amc_debug_filehandle.write("This is AutoMultipleChoice (Python translation sample)\n")
    _amc_debug_filehandle.write("Python: {} {}\n".format(sys.executable, sys.version))
    _amc_debug_filehandle.write("\n" + "="*40 + "\n\n")

    # Example: check "convert -version"
    if commande_accessible("convert"):
        p = subprocess.Popen(["convert", "-version"], stdout=subprocess.PIPE, text=True)
        out, _ = p.communicate()
        _amc_debug_filehandle.write(out + "\n")
    else:
        _amc_debug_filehandle.write("ImageMagick: not found\n")

    _amc_debug_filehandle.write("="*40 + "\n\n")

    # Example: check "gm -version"
    if commande_accessible("gm"):
        p = subprocess.Popen(["gm", "-version"], stdout=subprocess.PIPE, text=True)
        out, _ = p.communicate()
        _amc_debug_filehandle.write(out + "\n")
    else:
        _amc_debug_filehandle.write("GraphicsMagick: not found\n")

    _amc_debug_filehandle.write("="*40 + "\n\n")
    _amc_debug_filehandle.flush()

# -------------------------------------------------------------------------
# Basic path adaptation
# -------------------------------------------------------------------------
def amc_adapt_path(path=None, locals_=None, alt=None, file=None):
    """
    Equivalent to amc_adapt_path in the Perl code.
    """
    global amc_base_path
    if locals_ is None:
        locals_ = []
    if alt is None:
        alt = []

    p = []
    if path:
        p.append(path)
    if locals_:
        for item in locals_:
            p.append(os.path.join(amc_base_path, item))
    if alt:
        p.extend(alt)

    result = ''
    if file:
        # search among p for a directory containing 'file'
        for directory in p:
            candidate = os.path.join(directory, file)
            if os.path.isfile(candidate):
                result = candidate
                break
    else:
        # search among p for existing dir
        for directory in p:
            if os.path.isdir(directory):
                result = directory
                break
    return result

def amc_specdir(cls):
    """
    Equivalent to amc_specdir in the Perl code.
    """
    if cls in install_dirs:
        # Emulate the logic in the Perl code
        return amc_adapt_path(
            path=install_dirs[cls],
            locals_=[cls, '.'],
        )
    else:
        raise ValueError(f"Unknown class for amc_specdir: {cls}")

# -------------------------------------------------------------------------
# Searching for installed Perl modules: replaced with a placeholder in Python
# -------------------------------------------------------------------------
def perl_module_search(prefix):
    """
    In Perl, this scanned @INC for .pm files. In Python, there's no direct equivalent.
    We'll just return an empty list or a placeholder.
    """
    # *You* can implement a real search if needed.
    return []

# -------------------------------------------------------------------------
# Command-check utilities
# -------------------------------------------------------------------------
def commande_accessible(cmd, command_only=False):
    """
    Checks if a command is in the PATH or is an executable path.
    In the Perl code:
      - if $command_only=0, we strip arguments and only check the base command
      - if $command_only=1, we check the entire string
    Here we replicate that logic in Python.
    """
    if isinstance(cmd, list):
        for c in cmd:
            if c and commande_accessible(c, command_only):
                return True
        return False
    else:
        c = cmd.strip()
        if not command_only:
            # remove trailing arguments from the string
            c = c.split()[0]
        if "/" in c:
            return os.access(c, os.X_OK)
        else:
            # check PATH
            for path in os.getenv('PATH', '').split(os.pathsep):
                full = os.path.join(path, c)
                if os.access(full, os.X_OK):
                    return True
            return False

def system_debug(cmd_list, die_on_error=False):
    """
    Equivalent to system_debug in Perl.
    Runs a command (list of arguments), logs output to debug, etc.
    """
    debug("Calling cmd: {}".format(" ".join(cmd_list)))
    if not commande_accessible(cmd_list[0], command_only=True):
        msg = f"Can't find command: {cmd_list[0]}"
        debug_and_stderr(msg)
        if die_on_error:
            raise RuntimeError("Command failed")
        return -1

    process = subprocess.Popen(
        cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    pid = process.pid
    debug(f"CMD[{pid}] started")

    while True:
        line = process.stdout.readline()
        if not line:
            break
        line = line.rstrip('\n')
        debug(f"CMD[{pid}]> {line}")

    ret = process.wait()
    debug(f"CMD[{pid}] output ended")
    debug(f"CMD[{pid}] returns: {ret}")

    if ret != 0 and die_on_error:
        raise RuntimeError("Command failed with non-zero status")

    return ret

_gm_ok = commande_accessible('gm') and not os.getenv('AMC_DONT_USE_GM', '')

def magick_module(m):
    """
    Equivalent to 'magick_module' in Perl. Decides if we call 'gm' or directly 'm'.
    """
    if _gm_ok:
        return ['gm', m]
    else:
        return [m]

def use_gm_command():
    """
    Equivalent to 'use_gm_command' in Perl.
    """
    return _gm_ok

# We mimic the dynamic choice between Graphics::Magick and Image::Magick in Perl
# Here we'll just store a global variable, but Python usage is different.
_magick_pmodule = None

def magick_perl_module(dont_load_it=False):
    """
    Not directly meaningful in Python. We'll stub out.
    In Perl, it tries to load Graphics::Magick or Image::Magick.
    """
    global _magick_pmodule
    if not _magick_pmodule:
        # In Perl, we used check_install. In Python, we might attempt to import.
        for mod in ("wand.image", "PIL"):
            try:
                __import__(mod)
                _magick_pmodule = mod
                break
            except ImportError:
                pass
        if not _magick_pmodule:
            debug("*"*85)
            debug("ERROR: none of the python modules 'wand' or 'PIL' are available!")
            debug("AMC won't work properly.")
            debug("*"*85)
        else:
            if not dont_load_it:
                # We "import" it:
                __import__(_magick_pmodule)
                debug_pm_version(_magick_pmodule)
    return _magick_pmodule

def debug_pm_version(module_name):
    """
    In Perl, prints the module version. In Python, we can attempt something naive:
    """
    try:
        mod = sys.modules[module_name]
        ver = getattr(mod, '__version__', None)
        debug(f"[VERSION] {module_name}: {ver}")
    except KeyError:
        pass

# -------------------------------------------------------------------------
# Additional utilities
# -------------------------------------------------------------------------
def join_nonempty(sep, *args):
    """
    Just like the Perl join_nonempty.
    """
    filtered = [a for a in args if a]
    return sep.join(filtered)

def get_sty():
    """
    In Perl, calls "kpsewhich -all automultiplechoice.sty".
    We'll replicate that in Python.
    """
    try:
        out = subprocess.check_output(["kpsewhich", "-all", "automultiplechoice.sty"], text=True)
        return out.strip().split('\n')
    except Exception as e:
        debug(f"Cannot exec kpsewhich: {e}")
        return []

def file2id(f):
    """
    Equivalent to file2id in Perl.
    """
    m = re.match(r'^[a-z]*-?(\d+)-(\d+)-(\d+)', f)
    if m:
        return f"+{m.group(1)}/{m.group(2)}/{m.group(3)}+"
    else:
        return f

def id2idf(id_, simple=False):
    """
    Equivalent to id2idf in Perl.
    """
    x = re.sub(r'[\+/]+', '-', id_)
    x = re.sub(r'^-+', '', x)
    x = re.sub(r'-+$', '', x)
    if simple:
        # $id =~ s/([0-9]+-[0-9]+)-.*/$1/ if($oo{simple})
        m = re.match(r'(\d+-\d+)-.*', x)
        if m:
            x = m.group(1)
    return x

def get_qr(k):
    """
    Equivalent to get_qr in Perl.
    Q/A key parsing: (number).(number)
    """
    m = re.match(r'(\d+)\.(\d+)', k)
    if not m:
        raise ValueError(f"Unparsable Q/A key: {k}")
    return (int(m.group(1)), int(m.group(2)))

def get_epo(id_):
    """
    Equivalent to get_epo in Perl.
    """
    m = re.match(r'^\+?(\d+)/(\d+)/(\d+)\+?$', id_)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    else:
        return ()

def get_epc(id_):
    """
    Equivalent to get_epc in Perl.
    """
    m = re.match(r'^\+?(\d+)/(\d+)/(\d+)\+?$', id_)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    else:
        return ()

def get_ep(id_):
    """
    Equivalent to get_ep in Perl.
    If get_epo fails, we die in Perl => in Python, raise an exception.
    """
    r = get_epo(id_)
    if r:
        return r
    else:
        raise ValueError(f"Unparsable ID: {id_}")

def file_triable(f):
    """
    Equivalent to file_triable in Perl.
    """
    m = re.match(r'^[a-z]*-?(\d+)-(\d+)-(\d+)', f)
    if m:
        return f"{int(m.group(1)):50d}-{int(m.group(2)):30d}-{int(m.group(3)):40d}"
    else:
        return f

# The following sort_num, sort_string, sort_from_columns, attention, model_id_to_iter
# references a Gtk3::ListStore usage. In Python, you'd typically use PyGObject with
# a different approach. We provide stubs or no-ops to illustrate:

def sort_num(liststore, itera, iterb, sortkey):
    """
    Stub of numeric sort logic. In Python you'd implement differently.
    """
    return 0

def sort_string(liststore, itera, iterb, sortkey):
    """
    Stub of string sort logic.
    """
    return 0

def sort_from_columns(liststore, itera, iterb, sortkeys):
    """
    Stub for multi-column sort.
    """
    return 0

def attention(*msgs):
    """
    Print big starred messages.
    """
    lines = []
    for u in msgs:
        lines.extend(u.split('\n'))
    lm = max(len(x) for x in lines) if lines else 1
    print()
    print("*"*(lm+4))
    for l in lines:
        print("* " + l + " "*(lm-len(l)) + " *")
    print("*"*(lm+4))
    print()

# model_id_to_iter => stub
def model_id_to_iter(liststore, **constraints):
    """
    Stub for searching inside a GTK ListStore.
    """
    return None

# -------------------------------------------------------------------------
# Clearing old files
# -------------------------------------------------------------------------
def clear_old(filetype, *files):
    """
    Equivalent to clear_old in Perl: remove old file or directory content
    """
    for f in files:
        p = Path(f)
        if p.is_file():
            debug(f"Clearing old {filetype} file: {f}")
            p.unlink()
        elif p.is_dir():
            debug(f"Clearing old {filetype} directory: {f}")
            # remove all regular files in this directory
            # (not precisely the same as the original logic, but close)
            count = 0
            for child in p.iterdir():
                if child.is_file():
                    child.unlink()
                    count += 1
            debug(f"Removing {count} files.")

def new_filename(file):
    """
    Equivalent to new_filename in Perl.
    We create a new name if 'file' already exists.
    """
    p = Path(file)
    if not p.exists():
        return str(p)
    # Attempt to replicate the logic with underscore_NNNN
    match = re.match(r'^(.*?)(_?)(\d+)?(\.[a-z0-9]+)?$', file, flags=re.IGNORECASE)
    if match:
        prefix = match.group(1)
        underscore = match.group(2)
        n_str = match.group(3)
        suffix = match.group(4)
        if not suffix:
            suffix = ''
        try:
            n = int(n_str)
        except:
            n = 0

        return new_filename_compose(prefix, suffix, n)
    else:
        # fallback
        return new_filename_compose(file, '', 0)

def new_filename_compose(prefix, suffix, n):
    """
    Equivalent helper.
    """
    while True:
        n += 1
        candidate = f"{prefix}_{n:04d}{suffix}"
        if not os.path.exists(candidate):
            return candidate

def n_fich(dir_):
    """
    Equivalent to n_fich in Perl:
    returns ( number_of_files, first_filename )
    """
    try:
        entries = [e for e in os.listdir(dir_) if not e.startswith('.') and e != '__MACOSX']
        if not entries:
            return (0, None)
        return (len(entries), os.path.join(dir_, entries[0]))
    except Exception as e:
        debug(f"N_FICH : Can't open directory {dir_} : {e}")
        return (0, None)

def unzip_to_temp(file):
    """
    Equivalent to unzip_to_temp in Perl
    Extract a zip or tar.gz to a temp dir and return (temp_dir, error)
    """
    temp_dir = tempfile.mkdtemp()
    error = None
    cmd = []
    if re.search(r'\.zip$', file, re.IGNORECASE):
        cmd = ["unzip", "-d", temp_dir, file]
    else:
        # assume .tar.gz
        cmd = ["tar", "-x", "-v", "-z", "-f", file, "-C", temp_dir]

    debug(f"Extracting archive\nFROM: {file}\nWITH: {' '.join(cmd)}")
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in process.stdout:
            debug(line.rstrip('\n'))
        process.wait()
    except Exception as e:
        error = str(e)

    return (temp_dir, error)

# -------------------------------------------------------------------------
# pack_args, unpack_args, braces_if_necessary
# -------------------------------------------------------------------------
def braces_if_necessary(s):
    if not s:
        return f"\"{s}\""
    if re.search(r'[\s<>\{\}\(\)\[\];,\!\?\*\#\%]', s):
        return f"\"{s}\""
    return s

def pack_args(*args):
    """
    Equivalent to 'pack_args' in Perl, which writes arguments to an XML file.
    """
    tf = tempfile.NamedTemporaryFile(prefix='AMC-PACK-', suffix='.xml', dir=tempfile.gettempdir(), delete=False, mode='w', encoding='utf-8')
    tf.write('<?xml version="1.0" encoding="UTF-8"?>\n<arguments>\n')
    for a in args:
        tf.write(f"  <arg>{a}</arg>\n")
    tf.write("</arguments>\n")
    tf.close()
    return ["--xmlargs", tf.name]

def unpack_args(argv=None):
    """
    In Perl, we parse --debug=... --xmlargs=...
    We'll do a simple Python approach:
    """
    if argv is None:
        argv = sys.argv

    debug_val = None
    xmlargs_val = None
    keep = []
    i = 0
    while i < len(argv):
        if argv[i].startswith("--debug="):
            debug_val = argv[i].split("=",1)[1]
            i += 1
        elif argv[i].startswith("--xmlargs="):
            xmlargs_val = argv[i].split("=",1)[1]
            i += 1
        else:
            keep.append(argv[i])
            i += 1

    set_debug(debug_val)

    if xmlargs_val:
        # parse the xml file, read <arguments>, push them into keep
        import xml.etree.ElementTree as ET
        tree = ET.parse(xmlargs_val)
        root = tree.getroot()
        new_args = []
        for arg_node in root.findall('arg'):
            new_args.append(arg_node.text if arg_node.text else '')
        # Insert them into the front
        keep = new_args + keep

        # Unless debugging is on, remove the file
        if not get_debug():
            try:
                os.unlink(xmlargs_val)
            except:
                pass

        next_debug("Unpacked args: " + " ".join(braces_if_necessary(a) for a in new_args))
    return keep

def split_project_dir(project_dir):
    """
    Equivalent to split_project_dir in AMC::Basic:
    Returns (projects_home, project_name)
    """
    from os.path import realpath, dirname, basename
    project_dir = realpath(project_dir)
    # In Perl, it uses utf8::decode, etc. We'll skip that here.
    debug("ProjectDir: {}".format(project_dir))

    # simulate the splitting logic
    parent = dirname(project_dir)
    leaf = basename(project_dir)
    debug("- Projects directory: {}".format(parent))
    debug("- Project name: {}".format(leaf))
    return (parent, leaf)

def GetProjectOptions(bindings):
    """
    Stub for the big Perl function that used Getopt::Long + AMC::Path + AMC::Config.
    We can only partially replicate.
    """
    argv = unpack_args()
    # Typically, you'd parse with argparse in Python or similar.
    # Next steps: parse out --profile, --profile-conf, --project-dir
    # then do what the AMC::Config does. We'll do only placeholders.
    debug("GetProjectOptions invoked, but functionality is not fully replicated in Python.")

# -------------------------------------------------------------------------
# Localisation stubs
# -------------------------------------------------------------------------
_localisation = None
_titles = {}
_id_names = {}

def use_gettext():
    """
    In Perl, uses Locale::gettext->domain(). Here, we do a stub.
    """
    global _localisation
    _localisation = True
    init_translations()

def init_translations():
    """
    Fill _titles and _id_names with stub translations.
    """
    global _titles, _id_names
    _titles = {
        'nom': "Name",
        'note': "Mark",
        'copie': "Exam",
        'total': "Score",
        'max': "Max",
    }
    _id_names = {
        'max': "max",
        'moyenne': "mean",
    }

def __(s):
    """
    Stub for translation.
    """
    if not _localisation:
        # raise an error to mimic the original code
        raise RuntimeError("Needs use_gettext before __(...)")
    return s

def __p(s):
    """
    Stub for p-translation.
    We remove trailing bracketed text as in the original code.
    """
    t = __(s)
    t = re.sub(r'\s+\[.*\]\s*$', '', t)
    return t

def translate_column_title(k):
    return _titles.get(k, k)

def translate_id_name(k):
    return _id_names.get(k, k)

def format_date(time_):
    """
    Equivalent to format_date in Perl: strftime("%x %X", localtime).
    """
    return datetime.fromtimestamp(time_).strftime("%x %X")

def pageids_string(student, page, copy=None, path=False):
    s = f"{student}/{page}"
    if copy:
        s += f":{copy}"
    if path:
        s = re.sub(r'[^0-9]', '-', s)
    return s

def studentids_string(student, copy=None):
    student = student if student else ''
    return f"{student}:{copy}" if copy else student

def studentids_string_filename(student, copy=None):
    student = student if student else ''
    return f"{student}-{copy}" if copy else student

def annotate_source_change(capture, transaction):
    """
    Stub for 'annotate_source_change' in Perl.
    We'll just debug the time.
    """
    t = int(time.time())
    debug(f"Annotate source has changed! Time={t}")
    if transaction:
        # we don't have the concept of capture->begin_transaction
        pass
    # capture->variable('annotate_source_change', $t)
    if transaction:
        pass

def cb_model(*texte):
    """
    Stub for building a combobox model.
    In Python you'd typically use a list or Model. We'll return a list of (id, text).
    """
    pairs = []
    it = iter(texte)
    for k, t in zip(it, it):
        pairs.append((k, t))
    return pairs

def get_active_id(combo_widget):
    """
    Stub for "get_active_id".
    """
    # In a real Python/Gtk scenario, you'd do combo_widget.get_active_iter etc.
    # We'll just return an empty string.
    return ''

def check_fonts(spec):
    """
    Stubs the 'check_fonts' for 'fc-list' usage.
    """
    if 'type' in spec and re.search(r'fontconfig', spec['type'], re.IGNORECASE):
        if 'family' in spec and isinstance(spec['family'], list) and commande_accessible("fc-list"):
            # We do a minimal check
            # In Perl, we checked whether fc-list found anything for each family
            pass
    return True

def amc_user_confdir():
    """
    Just $HOME/.AMC.d
    """
    home = str(Path.home())
    return os.path.join(home, ".AMC.d")

def use_amc_plugins():
    """
    In Perl, we read the user plugin dir and add to @INC.
    In Python, we can do something else or just stub it.
    """
    debug("use_amc_plugins stub. (Would load Python plugins from ~/.AMC.d/plugins)")

def find_latex_file(file):
    """
    In Perl, we do 'kpsewhich -all file'. Return the first line if found.
    """
    if not commande_accessible("kpsewhich"):
        return None
    try:
        out = subprocess.check_output(["kpsewhich", "-all", file], text=True)
        lines = out.strip().split('\n')
        if lines:
            return lines[0]
        else:
            return None
    except:
        return None

def file_mimetype(file):
    """
    In Perl, tries File::MimeInfo::Magic. We'll do a naive approach in Python.
    """
    if file and os.path.isfile(file):
        # Minimal check
        if re.search(r'\.pdf$', file, re.IGNORECASE):
            return "application/pdf"
        else:
            return "application/octet-stream"
    return ''

def file_content(file):
    """
    Return the entire file content.
    """
    with open(file, 'rb') as f:
        return f.read()

def blob_to_file(blob):
    """
    Equivalent to writing a blob to a temp file.
    """
    tmp = tempfile.NamedTemporaryFile(prefix='AMC-IMAGE-', delete=False)
    tmp.write(blob)
    tmp.close()
    return tmp.name

def printable(s):
    """
    Return a printable version of s.
    """
    if s is None:
        return '<undef>'
    return str(s)

def string_to_usascii(s):
    """
    Convert to ascii, approximating the original logic with unaccent, etc.
    We'll do a simple approach in Python.
    """
    # If you have 'Unidecode', you might do: from unidecode import unidecode
    try:
        from unidecode import unidecode
        s = unidecode(s)
    except:
        # fallback: strip non-ascii
        pass
    s = re.sub(r'[^\x00-\x7f]', '_', s)
    return s

def show_utf8(s):
    """
    Stub for show_utf8.
    In Python3 strings are always unicode, so we'll just show s.
    """
    return s

def string_to_filename(s, prefix='f'):
    s = string_to_usascii(s)
    s = re.sub(r'[^a-zA-Z0-9.-]', '_', s)
    if not re.match(r'^[a-zA-Z0-9]', s):
        s = prefix + "_" + s
    return s

def path_to_filename(path):
    if path:
        return os.path.basename(path)
    return None

def glib_filename(n):
    """
    Stub for Glib::filename_display_name. We'll just return the filename in Python.
    """
    return n

def clean_gtk_filenames(*files):
    """
    Stub for 'clean_gtk_filenames'.
    In Perl, did unicode transformations.
    Here we do minimal or nothing.
    """
    return list(files)

def amc_component(name):
    """
    In Perl, sets $0 = ...
    In Python, that is possible but not recommended. We do a no-op or partial.
    """
    pass

def free_disk_mo(path):
    """
    Equivalent to free_disk_mo (using Filesys::Df).
    We can replicate with shutil.disk_usage in Python.
    Returns the free space in MB (approx).
    """
    try:
        usage = shutil.disk_usage(path)
        # usage.free is in bytes
        return usage.free // (1024**2)
    except:
        return None

def dir_contents_u(dir_):
    """
    Return directory contents without dot files.
    """
    try:
        out = []
        for x in os.listdir(dir_):
            if x.startswith('.'):
                continue
            if x == '__MACOSX':
                continue
            out.append(x)
        return out
    except Exception as e:
        debug_and_stderr(f"Error opening directory {dir_}: {e}")
        return []

# The very end of the Perl module: "1;"
# In Python, we just do the usual if __name__ == '__main__' block if needed.

if __name__ == '__main__':
    # Minimal usage example:
    print("Running AMC::Basic (Python translation) as a script.")
    print("Debug is:", get_debug())
    set_debug("stdout")
    debug("Test debug line.")
    set_debug(False)
    print("Debug is:", get_debug())
