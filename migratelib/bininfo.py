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


'''Locate and read information about executables'''


import errno
import os
import re
import subprocess


def find_bin(executable):
    for execdir in os.environ.get('PATH', '/usr/bin').split(':'):
        path = os.path.join(execdir, executable)
        try:
            fd = open(path, 'r')
            fd_path = '/proc/self/fd/%d' % fd.fileno()
            if os.access(fd_path, os.X_OK):
                return path, fd, fd_path
        except IOError as e:
            if e.errno == errno.ENOENT:
                continue
            raise
    else:
        raise OSError(errno.ENOENT, os.strerror(errno.ENOENT),
                      executable)


_linker_match_expression = r'''(?msx)   # 
\ {2}INTERP                             # line before starts INTERP
.*\[Requesting\ program\ interpreter:\  # interpreter is labelled
(?P<interp>.+)\]$                       # assume interpreter doesn't contain
                                        # ] followed by \n, so ends before that
'''


def read_linker(executable):
    argv = ['readelf', '--wide', '--program-headers', executable]
    out = subprocess.check_output(argv)
    m = re.search(_linker_match_expression, out)
    interp = m.group('interp')
    return interp


_find_libs_match_expression = r'''(?x)
\t(?P<name>.*)\ => # name is after a tab, and before the =>
\ (?P<path>.*)     # path follows the =>
\ \(0x[\da-f]+\)\n # line ends with the load address
'''


def find_libs(linker, executable):
    env = dict(os.environ)
    env['LD_TRACE_LOADED_OBJECTS'] = '1'
    argv = [linker, executable]
    out = subprocess.check_output(argv, env=env)
    for m in re.finditer(_find_libs_match_expression, out):
        if m:
            yield m.group('name'), m.group('path')
