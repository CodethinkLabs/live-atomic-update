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


'''Migrate process in a chroot in a namespace to a new root'''


from .genmounts import generate_mount_commands
from .migrate_process import migrate_process
from .mount_commands import mount_cmd, umount_cmd, findmnt_cmd
from .mount_tree import mount_tree


def migrate_root(root, pids, mount_list, replacements, mount_cmd=mount_cmd,
                 umount_cmd=umount_cmd, findmnt_cmd=findmnt_cmd):
    '''Migrate all pids in `pids` to `root`.
    
    If this is to be run in a different mount namespace, then pass canned
    equivalents of the *_cmd fields, as the namespace may not contain the
    necessary commands.

    '''
    with mount_tree(findmnt_cmd=findmnt_cmd, umount_cmd=umount_cmd) as new_tree:
        new_tree.mount(generate_mount_commands(mount_list=mount_list,
                                               replace=replacements,
                                               new_root=new_tree.root))

        for pid in pids:
            migrate_process(pid=pid, new_root=new_tree.root)

        with new_tree.pivot() as put_old:
            put_old.unmount(detach=True)
