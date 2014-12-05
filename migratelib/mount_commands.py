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


'''Utility command runners suitable for default values.

The *_cmd functions are supposed to be drop-in replaceable with smarter command
runners from the canned_command_runner module. These should not need to be used
directly, as library functions that use these, use them as the defaults.

'''


import subprocess


# Inconsistent argument passing conventions because the canned version of
# mount_cmd needs to know which argument is the source, as it may have to
# load it out of /proc umount_cmd only ever needs the target and findmnt_cmd's
# arguments are produced by find_mounts.
def mount_cmd(mountargs):
    '''Mount with args object as produced by generate_mount_commands'''
    return subprocess.check_call(['mount'] + mountargs.argv)


def umount_cmd(target, detach=False):
    '''Unmount target'''
    argv = ['umount']
    if detach:
        argv.append('-l')
    argv.append(target)
    return subprocess.check_call(argv)


def findmnt_cmd(argv):
    return subprocess.check_output(['findmnt'] + argv)
