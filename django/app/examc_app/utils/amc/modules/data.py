# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2022
# This file is part of Auto-Multiple-Choice (AMC).
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
# along with Auto-Multiple-Choice. If not, see <http://www.gnu.org/licenses/>.
import os
import re
import time

# ---------------------------------------------------
# Stubs / Placeholders for external references
# ---------------------------------------------------

def debug(msg):
    """Stub for the debug logging used in AMC::Basic."""
    print("[DEBUG]", msg)

def debug_and_stderr(msg):
    """Stub for debug + error channel logging."""
    # In your real environment, direct to logs or stderr
    print("[DEBUG]", msg)


class AMCDataModuleStub:
    """
    Stub class simulating the kind of object returned by
    AMC::DataModule::<module>. Replace or remove as needed.
    """
    def __init__(self, amcdata, **kwargs):
        self.amcdata = amcdata
        self.version_checked = kwargs.get('version_checked', None)
    # Additional methods as needed...


class AMCData:
    """
    Python translation of the Perl AMC::Data package.
    Manages data storage for AMC modules. Actual DB handling is replaced with stubs.
    """
    def __init__(self, directory, **oo):
        """
        Equivalent to AMC::Data->new($dir, %oo) in Perl.
        :param directory: path to the directory with the .sqlite files
        :param oo: additional optional parameters (on_error, progress, etc.)
        """
        self.directory = directory
        self.timeout = 300000
        self.dbh = None           # Stub for DB handle
        self.modules = {}
        self.version_checked = {}
        self.files = {}
        self.on_error = 'stdout,stderr,die'
        self.progress = ''
        self.trans = None         # Tracks whether a transaction is open

        # Override default values with anything in oo
        for k, v in oo.items():
            if hasattr(self, k):
                setattr(self, k, v)

        # Connect to the (stub) DB
        self.connect()

    def connect(self):
        """
        In Perl:
          $self->{dbh} = DBI->connect(...);
          ...
          # attach existing modules again
        Here, we use a stub for DB connection.
        """
        # Stub: no actual DB handle, but we simulate it
        self.dbh = "StubDBHandle"
        debug(f"Connecting (stub) with timeout={self.timeout}")

        # Clear modules references, re-load them if version_checked
        self.modules = {}
        for m in self.version_checked:
            debug(f"Connects module {m} ({self.version_checked[m]})")
            self.require_module(m, version_checked=self.version_checked[m])

    def disconnect(self):
        """
        In Perl:
          - Remember modules, then disconnect from DB
        """
        self.version_checked = {}
        if self.dbh:
            # Record the loaded modules, to re-load them upon reconnect
            for m in self.modules:
                mod_obj = self.modules[m]
                self.version_checked[m] = getattr(mod_obj, "version_checked", None)

            # "Disconnect" stub
            self.modules = {}
            self.dbh = None
            debug("Disconnected.")

    def sql_error(self, e):
        """
        In Perl:
          logs error, possibly prints, and dies
        """
        s = f"SQL ERROR: {e}\nSQL STATEMENT: ??? (stub)"
        debug(s)
        if 'stdout' in self.on_error:
            print(s)
        if 'stderr' in self.on_error:
            # In real code, might use sys.stderr
            print(s)
        if 'die' in self.on_error:
            raise RuntimeError("*SQL*")

    def directory(self):
        """
        Return the directory where the data is stored.
        """
        return self.directory

    def dbh_handle(self):
        """
        Return DB handle object (stub here).
        """
        return self.dbh

    def begin_transaction(self, key=None):
        """
        In Perl: sub begin_transaction { ... BEGIN IMMEDIATE ... }
        We track it in self.trans and log it.
        """
        if not key:
            key = '----'
        if self.trans:
            debug_and_stderr(f"WARNING: already opened transaction {self.trans} when starting {key}")
        debug(f"[{key}] BEGIN IMMEDIATE (stub)")
        # No real DB call
        self.trans = key

    def begin_read_transaction(self, key=None):
        """
        In Perl: sub begin_read_transaction { ... BEGIN ... }
        """
        if not key:
            key = '----'
        if self.trans:
            debug_and_stderr(f"WARNING: already opened transaction {self.trans} when starting {key}")
        debug(f"[{key}] BEGIN (stub)")
        self.trans = key

    def end_transaction(self, key=None):
        """
        In Perl: sub end_transaction { ... COMMIT ... }
        """
        if not key:
            key = '----'
        if self.trans != key:
            debug_and_stderr(f"WARNING: closing transaction {self.trans} declared as {key}")
        debug(f"[{key}] COMMIT (stub)")
        self.trans = None

    def sql_quote(self, string):
        """
        In Perl: $dbh->quote($string).
        Stub: just do a rough 'replace' or representation.
        """
        return "'"+string+"'"

    def sql_do(self, sql, *bind):
        """
        In Perl: executes the SQL with optional bind parameters.
        We log and do not actually run SQL in this stub.
        """
        if not self.trans and not re.match(r"^\s*(attach|begin)", sql, re.I):
            debug_and_stderr(f"WARNING: sql_do with no transaction -- {sql}")
        # Stub logging
        debug(f"SQL DO: {sql} | BIND: {bind}")

    def sql_tables(self, tables):
        """
        In Perl: returns $dbh->tables(...)
        Stub: return an empty list or a fixed list
        """
        return []

    def require_module(self, module, **oo):
        """
        In Perl:
          - attach the database: ATTACH DATABASE ? AS $module
          - load "AMC::DataModule::$module"
          - store an instance in self.modules{$module}
        """
        if module not in self.modules:
            filename = os.path.join(self.directory, module + ".sqlite")
            if not os.path.isfile(filename):
                debug(f"Creating non-existent database file for module {module}... (stub)")

            debug(f"Connecting to database {module}... (stub attach)")
            # self.dbh->{AutoCommit}=1 ; attach ; self.dbh->{AutoCommit}=0

            debug(f"Loading python module for AMC::DataModule::{module} (stub)")
            # In Perl, we do load("AMC::DataModule::$module")
            # Here we just create a stub module object
            mod_obj = AMCDataModuleStub(self, **oo)

            self.modules[module] = mod_obj
            self.files[module] = filename
            debug(f"Module {module} loaded (stub).")

    def module(self, module, **oo):
        """
        Return the module object for `module`. If not loaded, require it.
        """
        self.require_module(module, **oo)
        return self.modules[module]

    def module_path(self, module):
        """
        Return the path of the .sqlite file for this module,
        or None if it has not been loaded.
        """
        return self.files.get(module, None)

    def progression(self, action, argument):
        """
        In Perl: used by DataModule methods to indicate long actions for user feedback.
        We do a stub here.
        """
        # If self.progress is a callable or a dict with a 'Gtk3' object, etc.
        # Stub out the logic:
        if callable(self.progress):
            # e.g., self.progress(action, argument)
            pass
        elif isinstance(self.progress, dict):
            # Possibly UI-based. Stub the logic
            if action == 'begin':
                # handle text, fraction, etc.
                pass
            elif action == 'end':
                pass
            elif action == 'fraction':
                # update fraction
                # throttle updates to once per second
                pass

