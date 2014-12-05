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


'''Low-level binding for the setns syscall'''


import ctypes
import os


__all__ = ('nsenter',)


libc = ctypes.CDLL('libc.so.6', use_errno=True)


def nsenter(fd):
    ret = libc.setns(fd, 0)
    if ret < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), 'entering new namespace')
