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


import ctypes
import logging
import os


__all__ = ('pivot_root',)


libc = ctypes.CDLL('libc.so.6', use_errno=True)


def _pivot_root(new_root, put_old):
    ret = libc.pivot_root(new_root, put_old)
    if ret < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), 'pivoting root')


def pivot_root(new_root, put_old):
    logging.info('Pivoting into %s, putting old root into %s' % (new_root, put_old))
    _pivot_root(new_root, put_old)
    # Our paths for new_root and put_old are now wrong, so we need to strip
    # new_root from put_old and prepend new_root with put_old
    put_old = put_old[len(new_root):]
    if not os.path.isabs(put_old):
        put_old = '/' + put_old
    new_root = os.path.join(put_old, new_root.lstrip('/'))
    return new_root, put_old
