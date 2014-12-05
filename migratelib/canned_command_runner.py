#!/usr/bin/python
#
# Copyright (C) 2014 Codethink Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


'''Prepare commands that can be run in a namespace that only contains /proc.'''


import contextlib
import errno
import os
import subprocess
import sys

from .bininfo import find_bin, read_linker, find_libs


__all__ = ('root_fd', 'canned_mount_cmd', 'canned_umount_cmd',
           'canned_findmnt_cmd')


# 2.7.8 has a bug in fdopening a directory fd, so we need an alternative
# way to handle fd cleanup
if not sys.version_info >= (2, 7, 9):
    @contextlib.contextmanager
    def _closing_dir_fd(fd):
        try:
            yield
        finally:
            os.close(fd)


@contextlib.contextmanager
def root_fd():
    '''Open a file descriptor to your filesystem root to close on exit.
    
    This is a useful way to refer to resources outside your mount namespace
    or chroot, by looking up the file descriptor in /proc.
    
    '''
    # Unfortunately necessary. I generally prefer the file objects to handle
    # the life cycle, but fdopen on a directory fd is broken on 2.7.8, and
    # object destructors can't be reliably defined within python.
    root_fdno = os.open('/', os.O_DIRECTORY)
    if sys.version_info >= (2, 7, 9):
        cm = os.fdopen(root_fdno)
        os.close(root_fdno)
        root_fdno = cm.fileno()
    else:
        cm = _closing_dir_fd(root_fdno)
    with cm:
        yield root_fdno


def can_command(executable, root_fdno):
    root_fd_path = '/proc/self/fd/%d' % root_fdno
    if not os.path.isabs(executable):
        path, fobj, fd_path = find_bin(executable)
    else:
        path = executable
        fobj = open(path)
        fd_path = '/proc/self/fd/%d' % fobj.fileno()

    linker = read_linker(fd_path)

    libdirs = set()
    for libname, libpath in find_libs(linker, path):
        libdirs.add(os.path.dirname(libpath))
    ld_lib_path = ':'.join(os.path.join(root_fd_path, libdir.lstrip('/'))
                             for libdir in libdirs)

    canning_argv = [os.path.join(root_fd_path, linker.lstrip('/')),
                    '--library-path', ld_lib_path, fd_path]
    return canning_argv, fd


@contextlib.contextmanager
def canned_mount_cmd(root_fdno):
    '''Context manager that yields a mount_cmd that can be used from /proc'''
    canning_argv, execfobj = can_command(executable='mount', root_fdno=root_fdno)
    with execfobj:
        def mount_cmd(mountargs):
            return subprocess.check_call(canning_argv + mountargs.argv)
        yield mount_cmd


@contextlib.contextmanager
def canned_umount_cmd(root_fdno):
    '''Context manager that yields a umount_cmd that can be used from /proc'''
    canning_argv, execfobj = can_command(executable='umount', root_fdno=root_fdno)
    with execfobj:
        def umount_cmd(target, detach=False):
            argv = list(canning_argv)
            if detach:
                argv.append('-l')
            argv.append(target)
            return subprocess.check_call(argv)
        yield umount_cmd


@contextlib.contextmanager
def canned_findmnt_cmd(root_fdno):
    '''Context manager that yields a findmnt_cmd that can be used from /proc'''
    canning_argv, execfobj = can_command(executable='findmnt', root_fdno=root_fdno)
    with execfobj:
        def findmnt_cmd(argv):
            return subprocess.check_output(canning_argv + argv)
        yield findmnt_cmd
