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


'Generate mount arguments from a list of existing mounts and replacement rules'


import logging
import os
import warnings


__all__ = ('generate_mount_commands',)


class Mount(object):
    @property
    def argv(self):
        mnt_cmd = []
        if self.type is not None:
            mnt_cmd.extend(('-t', self.type))
        if self.options:
            mnt_cmd.extend(('-o', ','.join(self.options)))
        mnt_cmd.extend((self.source, self.target))
        return mnt_cmd


class BindMount(Mount):
    type = None
    options = ('bind',)
    def __init__(self, source, target):
        self.source = source
        self.target = target


class DiskMount(Mount):
    def __init__(self, source, target, type=None, options=()):
        self.source = source
        self.target = target
        self.type = type
        self.options = options
        

def generate_mount_commands(mount_list, replace, new_root):
    for mount in mount_list:
        new_target = os.path.join(new_root, mount['TARGET'].lstrip('/'))
        matching_filters = [(matches, mnt_opts)
                            for matches, mnt_opts in replace.iteritems()
                            if all(filter_key in mount
                                   and mount[filter_key] == filter_value
                                   for filter_key, filter_value in matches)]
        if len(matching_filters) > 1:
            warnings.warn('Filters multiple filters match mount %s'
                          % ' '.join('%s=%s' % pair for pair in mount.iteritems()))
        if matching_filters:
            matches, (mount_source, mount_type, mount_opts) = matching_filters[0]
            logging.info('mounting {src} to {tgt} with options {opts}'
                         .format(src=mount_source, tgt=new_target,
                                  opts=mount_opts))
            mnt_cmd = DiskMount(source=mount_source, target=new_target,
                                type=mount_type, options=mount_opts)
        else:
            logging.info('binding {src} to {tgt}'
                         .format(src=mount['TARGET'], tgt=new_target))
            mnt_cmd = BindMount(source=mount['TARGET'], target=new_target)
        yield mnt_cmd
