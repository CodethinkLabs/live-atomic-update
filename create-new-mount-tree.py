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


import argparse
import contextlib
import itertools
flatten = itertools.chain.from_iterable
import logging
import os
import shlex
import subprocess
import sys
import tempfile
import warnings


def create_arg_parser():
    replaceparser = argparse.ArgumentParser()

    class ReplaceAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            replacements = getattr(namespace, self.dest)
            newns, unparsed = replaceparser.parse_known_args(args=values)
            filters = frozenset(tuple(filter.split('=', 1))
                                for filter in sorted(flatten(newns.filter)))
            mount_options = ','.join(flatten(newns.mount_options))
            replacements[filters] = (newns.mount_source, newns.mount_type, mount_options)

    replaceparser.add_argument('--replace', nargs=argparse.REMAINDER,
                               action=ReplaceAction, default={})
    replaceparser.add_argument('--filter', nargs='*',
                               action='append', default=[])
    replaceparser.add_argument('--mount-source')
    replaceparser.add_argument('--mount-type')
    replaceparser.add_argument('--mount-options', '-o', nargs='*', action='append',
                               default=[])
    
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid', type=int)
    ap.add_argument('--replace', nargs=argparse.REMAINDER, action=ReplaceAction,
                    default={}, metavar='MOUNTPOINT')
    return ap


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

def find_mounts(root=None, task=None, fields=None, recurse=False):
    argv = ['findmnt', '--pairs', '--nofsroot']
    if task is not None:
        argv.extend(('--task', str(task)))
    if fields is not None:
        argv.extend(('--output', ','.join(fields)))
    if recurse:
        if root is not None:
            raise ValueError('recurse passed without root')
        argv.append('--submounts')
    if root is not None:
        argv.append(root)
    o = subprocess.check_output(argv)
    mount_list = []
    for line in o.splitlines():
        matches = dict()
        for pair in shlex.split(line):
            key, value = pair.split('=', 1)
            matches[key] = value.decode('string_escape')
        mount_list.append(matches)
    return mount_list


@contextlib.contextmanager
def new_mount_tree():
    alternative_tree = tempfile.mkdtemp(suffix='\nhaha newline')
    try:
        yield alternative_tree
    except BaseException as e:
        (etype, evalue, etrace) = sys.exc_info()
        try:
            for mount in reversed(find_mounts(root=alternative_tree)):
                subprocess.call(['umount', mount['TARGET']])
        except CalledProcessError as e:
            pass
        else:
            os.rmdir(alternative_tree)
        raise etype, evalue, etrace


def run():
    ap = create_arg_parser()
    opts = ap.parse_args(['--pid', '1',
                          '--replace', '--filter', 'TARGET=/', 'FSTYPE=btrfs',
                              '--mount-source', '/dev/sda', '--mount-type=btrfs',
                              '-osubvol=/systems/criu2/run', '-o', 'rw',
                         ])
    opts = ap.parse_args()
    mount_list = find_mounts(task=opts.pid, fields=search_fields)

    with new_mount_tree() as alternative_tree:
        for mount in mount_list:
            new_target = os.path.join(alternative_tree, mount['TARGET'].lstrip('/'))
            matching_filters = [(matches, mnt_opts)
                                for matches, mnt_opts in opts.replace.iteritems()
                                if all(filter_key in mount
                                       and mount[filter_key] == filter_value
                                       for filter_key, filter_value in matches)]
            if len(matching_filters) > 1:
                warnings.warn('Filters multiple filters match mount %s'
                              % ' '.join('%s=%s' % pair for pair in mount.iteritems()))
            if not os.path.exists(new_target):
                os.makedirs(new_target)
            if matching_filters:
                matches, (mount_source, mount_type, mount_opts) = matching_filters[0]
                logging.info('mounting {src} to {tgt} with options {opts}'
                             .format(src=mount_source, tgt=new_target,
                                      opts=mount_opts))
                mnt_cmd = ['mount']
                if mount_type is not None:
                    mnt_cmd.extend(('-t', mount_type))
                if mount_opts:
                    mnt_cmd.extend(('-o', mount_opts))
                mnt_cmd.extend((mount_source, new_target))
            else:
                logging.info('binding {src} to {tgt}'
                             .format(src=mount_source, tgt=mount['TARGET']))
                mnt_cmd = ['mount', '--bind', mount['TARGET'], new_target]
            subprocess.check_call(mnt_cmd)
        print alternative_tree


if __name__ == '__main__':
    run()
