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


'''Migrate process in a namespace to a new root'''


import logging
import os

from .findmnt import find_mounts, search_fields
from .migrate_root import migrate_root
from .mount_commands import mount_cmd, umount_cmd, findmnt_cmd


__all__ = ('migrate_namespace',)


def migrate_namespace(namespace, pids_in_root, replacements,
                      mount_cmd=mount_cmd, umount_cmd=umount_cmd,
                      findmnt_cmd=findmnt_cmd):
    with namespace.entered():
        if not os.path.isdir('/proc'):
            logging.info('Skipping %s' % namespace)
        for root, pids in pids_in_root.iteritems():
            mount_list = find_mounts(root=root,
                                     tab_file='/proc/self/fd/%d'
                                         % namespace.mountinfo_fobj.fileno(),
                                     fields=search_fields, recurse=True,
                                     runcmd=findmnt_cmd)
            migrate_root(root, pids, mount_list, replacements,
                         mount_cmd=mount_cmd, umount_cmd=umount_cmd,
                         findmnt_cmd=findmnt_cmd)


def run():
    import argparse
    import logging
    import os
    import sys
    from .namespace import MountNamespace
    from . import replaceparser
    from .list_processes import collect_process_info
    from .canned_command_runner import (root_fd, canned_mount_cmd,
                                        canned_umount_cmd, canned_findmnt_cmd)

    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--namespace', default='/proc/self/ns/mnt')
    replaceparser.extend_arg_parser(ap)
    opts = ap.parse_args()
    print opts

    with open(opts.namespace) as mount_ns_fobj, \
         open(os.path.normpath(os.path.join(opts.namespace, '../../mountinfo'))) \
             as mountinfo_fobj:
        ns = MountNamespace(mount_ns_fobj, mountinfo_fobj)
        procinfo = collect_process_info()

        with root_fd() as root_fdno, \
             canned_mount_cmd(root_fdno) as mount_cmd, \
             canned_umount_cmd(root_fdno) as umount_cmd, \
             canned_findmnt_cmd(root_fdno) as findmnt_cmd:
            migrate_namespace(namespace=ns, pids_in_root=procinfo[ns],
                              replacements=opts.replace, mount_cmd=mount_cmd,
                              umount_cmd=umount_cmd, findmnt_cmd=findmnt_cmd)


if __name__ == '__main__':
    run()
