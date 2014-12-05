#!/usr/bin/python
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


'List all the namespaces and chroots that need to be migrated'


import argparse
import collections
import ctypes
import os
import tempfile

from .namespace import MountNamespace


__all__ = ('collect_process_info',)


def create_arg_parser():
    ap = argparse.ArgumentParser(description=__doc__)
    return ap


def collect_process_info():
    #procinfo[ns][root] = set(pid)
    procinfo = collections.defaultdict(lambda: collections.defaultdict(set))
    for pid_dir in os.listdir('/proc'):
        try:
            pid = int(pid_dir, base=10)
        except ValueError as e:
            continue
        mountns = MountNamespace.from_pid(pid)
        root = os.readlink(os.path.join('/proc', pid_dir, 'root'))
        procinfo[mountns][root].add(pid)
    return procinfo


def run():
    import pprint
    ap = create_arg_parser()
    opts = ap.parse_args()

    procinfo = collect_process_info()
    pprint.pprint(dict(procinfo))


if __name__ == '__main__':
    run()
