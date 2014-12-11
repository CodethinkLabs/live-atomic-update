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


'Find information about mounts'


import shlex
import subprocess

from .mount_commands import mount_cmd, umount_cmd, findmnt_cmd


__all__ = ('search_fields', 'find_mounts')


search_fields = [
       'SOURCE', # source device
       'TARGET', # mountpoint
       'FSTYPE', # filesystem type
      'OPTIONS', # all mount options
  'VFS-OPTIONS', # VFS specific mount options
   'FS-OPTIONS', # FS specific mount options
        'LABEL', # filesystem label
         'UUID', # filesystem UUID
    'PARTLABEL', # partition label
     'PARTUUID', # partition UUID
      'MAJ:MIN', # major:minor device number
       'FSROOT', # filesystem root
          'TID', # task ID
           'ID', # mount ID
   'OPT-FIELDS', # optional mount fields
  'PROPAGATION', # VFS propagation flags
]


def find_mounts(root=None, tab_file=None, task=None, fields=None,
                recurse=False, runcmd=findmnt_cmd):
    argv = ['--pairs', '--nofsroot']
    if task is not None:
        argv.extend(('--task', str(task)))
    if tab_file is not None:
        argv.extend(('--tab-file', str(tab_file)))
    if fields is not None:
        argv.extend(('--output', ','.join(fields)))
    if recurse:
        if root is None:
            raise ValueError('recurse passed without root')
        argv.append('--submounts')
    if root is not None:
        argv.append(root)
    o = runcmd(argv)

    mount_list = []
    for line in o.splitlines():
        matches = dict()
        for pair in shlex.split(line):
            key, value = pair.split('=', 1)
            matches[key] = value.decode('string_escape')
        mount_list.append(matches)
    return mount_list
