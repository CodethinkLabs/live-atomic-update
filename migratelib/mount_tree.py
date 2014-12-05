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


'Replicate the mount tree of a process with alterations.'


import contextlib
import os
import subprocess
import sys
import tempfile

from .findmnt import find_mounts, search_fields
from .genmounts import generate_mount_commands
from .mount_commands import mount_cmd, umount_cmd, findmnt_cmd
#import .replaceparser as replaceparser
from . import replaceparser


__all__ = ('mount_tree', 'mount_new_root')


class MountTree(object):
    ''''''
    def __init__(self, root, mount_cmd, umount_cmd, findmnt_cmd):
        self.root = root
        self.mount_cmd = mount_cmd
        self.umount_cmd = umount_cmd
        self.findmnt_cmd = findmnt_cmd

    def mount(self, mountargs_list):
        for mountargs in mountargs_list:
            if not os.path.exists(mountargs.target):
                os.makedirs(mountargs.target)
            self.mount_cmd(mountargs)

    @contextlib.contextmanager
    def pivot(self, tempdir='/tmp'):
        '''Change root the new tree.
        
        If an exception is raised in the context, then it pivots back.
        This returns a MountTree object that can be `unmount()`ed

        
        '''
        tempdir = os.path.join(self.root, tempdir.lstrip('/'))
        with mount_tree(tempdir=tempdir, mount_cmd=self.mount_cmd,
                        umount_cmd=self.umount_cmd,
                        findmnt_cmd=self.findmnt_cmd) as old_tree:
            try:
                yield old_tree
            except BaseException as e:
                self.root, old_tree.root = pivot_root(new_root=self.root,
                                                      put_old=old_tree.root)


@contextlib.contextmanager
def mount_tree(tempdir=None, mount_cmd=mount_cmd, umount_cmd=umount_cmd,
               findmnt_cmd=findmnt_cmd):
    '''Context for a mount tree that is cleaned up.
    
    `dir` can be passed to specify an alternative temporary directory

    the returned NewTree object has a .mount method that takes a list of mount
    arguments, as returned from generate_mount_commands.
    
    Any mounts under the returned tree are unmounted on exception, and left
    mounted on regular exit.
    
    '''
    tree_dir = tempfile.mkdtemp(dir=tempdir)
    new_tree = MountTree(root=tree_dir, mount_cmd=mount_cmd,
                         umount_cmd=umount_cmd, findmnt_cmd=findmnt_cmd)
    try:
        yield new_tree
    except BaseException as e:
        (etype, evalue, etrace) = sys.exc_info()
        try:
            for mount in reversed(find_mounts(root=new_tree.root,
                                              runcmd=findmnt_cmd)):
                umount_cmd([mount['TARGET']])
        except subprocess.CalledProcessError as e:
            pass
        else:
            os.rmdir(alternative_tree)
        raise etype, evalue, etrace


def create_arg_parser():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid', type=int)
    ap.add_argument('--test', action='store_const', const=True, default=False)
    replaceparser.extend_arg_parser(ap)
    return ap


def run():
    ap = create_arg_parser()
    opts = ap.parse_args()
    if opts.test:
        opts = ap.parse_args(
            ['--pid', '1',
                '--replace', '--filter', 'TARGET=/', 'FSTYPE=btrfs',
                    '--mount-source', '/dev/sda', '--mount-type=btrfs',
                    '-osubvol=/systems/criu2/run', '-o', 'rw',
            ])
    mount_list = find_mounts(task=opts.pid, fields=search_fields)

    with new_mount_tree() as new_tree:
        new_tree.mount(generate_mount_commands(mount_list, opts.replace))
        print new_tree.root


if __name__ == '__main__':
    run()
