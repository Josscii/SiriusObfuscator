﻿"""
Test that breakpoint by symbol name works correctly with dynamic libs.
"""

from __future__ import print_function


import os
import time
import re
import lldb
from lldbsuite.test.decorators import *
from lldbsuite.test.lldbtest import *
from lldbsuite.test import lldbutil


@skipIfWindows  # Windows doesn't have dlopen and friends, dynamic libraries work differently
class LoadUnloadTestCase(TestBase):

    def getCategories(self):
        return ['basic_process']

    mydir = TestBase.compute_mydir(__file__)

    def setUp(self):
        # Call super's setUp().
        TestBase.setUp(self)
        # Find the line number to break for main.cpp.
        self.line = line_number(
            'main.cpp',
            '// Set break point at this line for test_lldb_process_load_and_unload_commands().')
        self.line_d_function = line_number(
            'd.cpp', '// Find this line number within d_dunction().')
        if not self.platformIsDarwin():
            if not lldb.remote_platform and "LD_LIBRARY_PATH" in os.environ:
                self.runCmd(
                    "settings set target.env-vars " +
                    self.dylibPath +
                    "=" +
                    os.environ["LD_LIBRARY_PATH"] +
                    ":" +
                    os.getcwd())
            else:
                if lldb.remote_platform:
                    wd = lldb.remote_platform.GetWorkingDirectory()
                else:
                    wd = os.getcwd()
                self.runCmd(
                    "settings set target.env-vars " +
                    self.dylibPath +
                    "=" +
                    wd)

    def copy_shlibs_to_remote(self, hidden_dir=False):
        """ Copies the shared libs required by this test suite to remote.
        Does nothing in case of non-remote platforms.
        """
        if lldb.remote_platform:
            cwd = os.getcwd()
            shlibs = ['libloadunload_a.so', 'libloadunload_b.so',
                      'libloadunload_c.so', 'libloadunload_d.so']
            wd = lldb.remote_platform.GetWorkingDirectory()
            for f in shlibs:
                err = lldb.remote_platform.Put(
                    lldb.SBFileSpec(os.path.join(cwd, f)),
                    lldb.SBFileSpec(os.path.join(wd, f)))
                if err.Fail():
                    raise RuntimeError(
                        "Unable copy '%s' to '%s'.\n>>> %s" %
                        (f, wd, err.GetCString()))
            if hidden_dir:
                shlib = 'libloadunload_d.so'
                hidden_dir = os.path.join(wd, 'hidden')
                hidden_file = os.path.join(hidden_dir, shlib)
                err = lldb.remote_platform.MakeDirectory(hidden_dir)
                if err.Fail():
                    raise RuntimeError(
                        "Unable to create a directory '%s'." % hidden_dir)
                err = lldb.remote_platform.Put(
                    lldb.SBFileSpec(os.path.join(cwd, 'hidden', shlib)),
                    lldb.SBFileSpec(hidden_file))
                if err.Fail():
                    raise RuntimeError(
                        "Unable copy 'libloadunload_d.so' to '%s'.\n>>> %s" %
                        (wd, err.GetCString()))

    @skipIfFreeBSD  # llvm.org/pr14424 - missing FreeBSD Makefiles/testcase support
    @not_remote_testsuite_ready
    @skipIfWindows  # Windows doesn't have dlopen and friends, dynamic libraries work differently
    def test_modules_search_paths(self):
        """Test target modules list after loading a different copy of the library libd.dylib, and verifies that it works with 'target modules search-paths add'."""

        # Invoke the default build rule.
        self.build()

        if self.platformIsDarwin():
            dylibName = 'libloadunload_d.dylib'
        else:
            dylibName = 'libloadunload_d.so'

        # The directory with the dynamic library we did not link to.
        new_dir = os.path.join(os.getcwd(), "hidden")

        old_dylib = os.path.join(os.getcwd(), dylibName)
        new_dylib = os.path.join(new_dir, dylibName)

        exe = os.path.join(os.getcwd(), "a.out")
        self.runCmd("file " + exe, CURRENT_EXECUTABLE_SET)

        self.expect("target modules list",
                    substrs=[old_dylib])
        # self.expect("target modules list -t 3",
        #    patterns = ["%s-[^-]*-[^-]*" % self.getArchitecture()])
        # Add an image search path substitution pair.
        self.runCmd(
            "target modules search-paths add %s %s" %
            (os.getcwd(), new_dir))

        self.expect("target modules search-paths list",
                    substrs=[os.getcwd(), new_dir])

        self.expect(
            "target modules search-paths query %s" %
            os.getcwd(),
            "Image search path successfully transformed",
            substrs=[new_dir])

        # Obliterate traces of libd from the old location.
        os.remove(old_dylib)
        # Inform (DY)LD_LIBRARY_PATH of the new path, too.
        env_cmd_string = "settings set target.env-vars " + self.dylibPath + "=" + new_dir
        if self.TraceOn():
            print("Set environment to: ", env_cmd_string)
        self.runCmd(env_cmd_string)
        self.runCmd("settings show target.env-vars")

        remove_dyld_path_cmd = "settings remove target.env-vars " + self.dylibPath
        self.addTearDownHook(
            lambda: self.dbg.HandleCommand(remove_dyld_path_cmd))

        self.runCmd("run")

        self.expect(
            "target modules list",
            "LLDB successfully locates the relocated dynamic library",
            substrs=[new_dylib])

    @skipIfFreeBSD  # llvm.org/pr14424 - missing FreeBSD Makefiles/testcase support
    @expectedFailureAndroid  # wrong source file shows up for hidden library
    @skipIfWindows  # Windows doesn't have dlopen and friends, dynamic libraries work differently
    def test_dyld_library_path(self):
        """Test (DY)LD_LIBRARY_PATH after moving libd.dylib, which defines d_function, somewhere else."""

        # Invoke the default build rule.
        self.build()
        self.copy_shlibs_to_remote(hidden_dir=True)

        exe = os.path.join(os.getcwd(), "a.out")
        self.runCmd("file " + exe, CURRENT_EXECUTABLE_SET)

        # Shut off ANSI color usage so we don't get ANSI escape sequences
        # mixed in with stop locations.
        self.dbg.SetUseColor(False)

        if self.platformIsDarwin():
            dylibName = 'libloadunload_d.dylib'
            dsymName = 'libloadunload_d.dylib.dSYM'
        else:
            dylibName = 'libloadunload_d.so'

        # The directory to relocate the dynamic library and its debugging info.
        special_dir = "hidden"
        if lldb.remote_platform:
            wd = lldb.remote_platform.GetWorkingDirectory()
        else:
            wd = os.getcwd()

        old_dir = wd
        new_dir = os.path.join(wd, special_dir)
        old_dylib = os.path.join(old_dir, dylibName)

        remove_dyld_path_cmd = "settings remove target.env-vars " + self.dylibPath
        self.addTearDownHook(
            lambda: self.dbg.HandleCommand(remove_dyld_path_cmd))

        # For now we don't track (DY)LD_LIBRARY_PATH, so the old library will be in
        # the modules list.
        self.expect("target modules list",
                    substrs=[os.path.basename(old_dylib)],
                    matching=True)

        lldbutil.run_break_set_by_file_and_line(
            self, "d.cpp", self.line_d_function, num_expected_locations=1)
        # After run, make sure the non-hidden library is picked up.
        self.expect("run", substrs=["return", "700"])

        self.runCmd("continue")

        # Add the hidden directory first in the search path.
        env_cmd_string = ("settings set target.env-vars %s=%s" %
                          (self.dylibPath, new_dir))
        if not self.platformIsDarwin():
            env_cmd_string += ":" + wd
        self.runCmd(env_cmd_string)

        # This time, the hidden library should be picked up.
        self.expect("run", substrs=["return", "12345"])

    @expectedFailureAll(
        bugnumber="llvm.org/pr25805",
        hostoslist=["windows"],
        compiler="gcc",
        archs=["i386"],
        triple='.*-android')
    @skipIfFreeBSD  # llvm.org/pr14424 - missing FreeBSD Makefiles/testcase support
    @skipIfWindows  # Windows doesn't have dlopen and friends, dynamic libraries work differently
    def test_lldb_process_load_and_unload_commands(self):
        """Test that lldb process load/unload command work correctly."""

        # Invoke the default build rule.
        self.build()
        self.copy_shlibs_to_remote()

        exe = os.path.join(os.getcwd(), "a.out")
        self.runCmd("file " + exe, CURRENT_EXECUTABLE_SET)

        # Break at main.cpp before the call to dlopen().
        # Use lldb's process load command to load the dylib, instead.

        lldbutil.run_break_set_by_file_and_line(
            self, "main.cpp", self.line, num_expected_locations=1, loc_exact=True)

        self.runCmd("run", RUN_SUCCEEDED)

        if lldb.remote_platform:
            shlib_dir = lldb.remote_platform.GetWorkingDirectory()
        else:
            shlib_dir = self.mydir

        if self.platformIsDarwin():
            dylibName = 'libloadunload_a.dylib'
        else:
            dylibName = 'libloadunload_a.so'

        # Make sure that a_function does not exist at this point.
        self.expect(
            "image lookup -n a_function",
            "a_function should not exist yet",
            error=True,
            matching=False,
            patterns=["1 match found"])

        # Use lldb 'process load' to load the dylib.
        self.expect(
            "process load %s --install" %
            dylibName,
            "%s loaded correctly" %
            dylibName,
            patterns=[
                'Loading "%s".*ok' %
                dylibName,
                'Image [0-9]+ loaded'])

        # Search for and match the "Image ([0-9]+) loaded" pattern.
        output = self.res.GetOutput()
        pattern = re.compile("Image ([0-9]+) loaded")
        for l in output.split(os.linesep):
            #print("l:", l)
            match = pattern.search(l)
            if match:
                break
        index = match.group(1)

        # Now we should have an entry for a_function.
        self.expect(
            "image lookup -n a_function",
            "a_function should now exist",
            patterns=[
                "1 match found .*%s" %
                dylibName])

        # Use lldb 'process unload' to unload the dylib.
        self.expect(
            "process unload %s" %
            index,
            "%s unloaded correctly" %
            dylibName,
            patterns=[
                "Unloading .* with index %s.*ok" %
                index])

        self.runCmd("process continue")

    @skipIfFreeBSD  # llvm.org/pr14424 - missing FreeBSD Makefiles/testcase support
    def test_load_unload(self):
        """Test breakpoint by name works correctly with dlopen'ing."""

        # Invoke the default build rule.
        self.build()
        self.copy_shlibs_to_remote()

        exe = os.path.join(os.getcwd(), "a.out")
        self.runCmd("file " + exe, CURRENT_EXECUTABLE_SET)

        # Break by function name a_function (not yet loaded).
        lldbutil.run_break_set_by_symbol(
            self, "a_function", num_expected_locations=0)

        self.runCmd("run", RUN_SUCCEEDED)

        # The stop reason of the thread should be breakpoint and at a_function.
        self.expect("thread list", STOPPED_DUE_TO_BREAKPOINT,
                    substrs=['stopped',
                             'a_function',
                             'stop reason = breakpoint'])

        # The breakpoint should have a hit count of 1.
        self.expect("breakpoint list -f", BREAKPOINT_HIT_ONCE,
                    substrs=[' resolved, hit count = 1'])

        # Issue the 'contnue' command.  We should stop agaian at a_function.
        # The stop reason of the thread should be breakpoint and at a_function.
        self.runCmd("continue")

        # rdar://problem/8508987
        # The a_function breakpoint should be encountered twice.
        self.expect("thread list", STOPPED_DUE_TO_BREAKPOINT,
                    substrs=['stopped',
                             'a_function',
                             'stop reason = breakpoint'])

        # The breakpoint should have a hit count of 2.
        self.expect("breakpoint list -f", BREAKPOINT_HIT_ONCE,
                    substrs=[' resolved, hit count = 2'])

    @skipIfFreeBSD  # llvm.org/pr14424 - missing FreeBSD Makefiles/testcase support
    @skipIfWindows  # Windows doesn't have dlopen and friends, dynamic libraries work differently
    def test_step_over_load(self):
        """Test stepping over code that loads a shared library works correctly."""

        # Invoke the default build rule.
        self.build()
        self.copy_shlibs_to_remote()

        exe = os.path.join(os.getcwd(), "a.out")
        self.runCmd("file " + exe, CURRENT_EXECUTABLE_SET)

        # Break by function name a_function (not yet loaded).
        lldbutil.run_break_set_by_file_and_line(
            self, "main.cpp", self.line, num_expected_locations=1, loc_exact=True)

        self.runCmd("run", RUN_SUCCEEDED)

        # The stop reason of the thread should be breakpoint and at a_function.
        self.expect("thread list", STOPPED_DUE_TO_BREAKPOINT,
                    substrs=['stopped',
                             'stop reason = breakpoint'])

        self.runCmd(
            "thread step-over",
            "Stepping over function that loads library")

        # The stop reason should be step end.
        self.expect("thread list", "step over succeeded.",
                    substrs=['stopped',
                             'stop reason = step over'])

    @skipIfFreeBSD  # llvm.org/pr14424 - missing FreeBSD Makefiles/testcase support
    @skipIfWindows  # Windows doesn't have dlopen and friends, dynamic libraries work differently
    @unittest2.expectedFailure("llvm.org/pr25806")
    def test_static_init_during_load(self):
        """Test that we can set breakpoints correctly in static initializers"""

        self.build()
        self.copy_shlibs_to_remote()

        exe = os.path.join(os.getcwd(), "a.out")
        self.runCmd("file " + exe, CURRENT_EXECUTABLE_SET)

        a_init_bp_num = lldbutil.run_break_set_by_symbol(
            self, "a_init", num_expected_locations=0)
        b_init_bp_num = lldbutil.run_break_set_by_symbol(
            self, "b_init", num_expected_locations=0)
        d_init_bp_num = lldbutil.run_break_set_by_symbol(
            self, "d_init", num_expected_locations=1)

        self.runCmd("run", RUN_SUCCEEDED)

        self.expect("thread list", STOPPED_DUE_TO_BREAKPOINT,
                    substrs=['stopped',
                             'd_init',
                             'stop reason = breakpoint %d' % d_init_bp_num])

        self.runCmd("continue")
        self.expect("thread list", STOPPED_DUE_TO_BREAKPOINT,
                    substrs=['stopped',
                             'a_init',
                             'stop reason = breakpoint %d' % a_init_bp_num])
        self.expect("thread backtrace",
                    substrs=['a_init',
                             'dlopen',
                             'main'])

        self.runCmd("continue")
        self.expect("thread list", STOPPED_DUE_TO_BREAKPOINT,
                    substrs=['stopped',
                             'b_init',
                             'stop reason = breakpoint %d' % b_init_bp_num])
        self.expect("thread backtrace",
                    substrs=['b_init',
                             'dlopen',
                             'main'])