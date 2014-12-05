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


'''Namespace object that '''


import contextlib
import os

from .ll.nsenter import nsenter


__all__ = ('Namespace',)


class MountNamespace(object):

    def __init__(self, mount_ns_fobj, mountinfo_fobj):
        self.mount_ns_fobj = mount_ns_fobj
        self.mountinfo_fobj = mountinfo_fobj
        self.inode = os.fstat(mount_ns_fobj.fileno()).st_ino

    @classmethod
    def from_pid(cls, pid):
        proc_path = '/proc/%d' % pid
        ns_path = os.path.join(proc_path, 'ns', 'mnt')
        mount_ns_fobj = open(ns_path)
        # We're kind of screwed if processes change namespace out from under
        # us, but let's avoid the fd and the magic inode getting out of sync
        # here anyway, since we're likely to get better diagnostics
        mountinfo_path = os.path.join(proc_path, 'mountinfo')
        mountinfo_fobj = open(mountinfo_path)
        cls(mount_ns_fobj=mount_ns_fobj, mountinfo_fobj=mouninfo_fobj)

    def __hash__(self):
        return hash(self.inode)

    def __eq__(self, other):
        return self.inode == other.inode

    def __str__(self):
        return 'Namespace(%d)' % self.inode

    @contextlib.contextmanager
    def entered(self):
        current_ns = open('/proc/self/ns/mnt')
        nsenter(self.mount_ns_fobj.fileno())
        try:
            yield
        finally:
            nsenter(current_ns.fileno())
