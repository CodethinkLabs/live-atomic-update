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

'''Migrate process to new root'''

import argparse
import json
import logging
import os
import pipes
import subprocess
import sys
import warnings

def create_arg_parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid', type=int)
    ap.add_argument('--root')
    ap.add_argument('--debug', default=False, action='store_const',
                    const=True)
    return ap


def get_pid_cwd(pid):
    return os.readlink(os.path.join('/proc', str(pid), 'cwd'))


def get_pid_root(pid):
    return os.readlink(os.path.join('/proc', str(pid), 'root'))


def get_pid_dir_fds(pid):
    fds_dir = os.path.join('/proc', str(pid), 'fd')
    for fileno in os.listdir(fds_dir):
        fd_link = os.path.join(fds_dir, fileno)
        if os.path.isdir(fd_link):
            yield int(fileno), os.readlink(fd_link)


def run_gdb_cmd_in_pid(command, pid):
    argv = ['gdb', '--quiet', '--pid', str(pid), '--batch',
            '--eval-command', command]
    with open(os.devnull) as devnull:
        out = subprocess.check_output(argv, stderr=devnull)
        ecode = int(out.splitlines()[-1].strip())
    logging.debug('Running %s returned %d' %
                  (' '.join(map(pipes.quote, argv)), ecode))
    return ecode


def run():
    ap = create_arg_parser()
    opts = ap.parse_args()

    if opts.debug:
        logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    old_root = get_pid_root(opts.pid)
    if not opts.root.startswith(old_root):
        raise Exception('New root not reachable from old root')

    old_cwd = get_pid_cwd(opts.pid)
    old_dir_fds = get_pid_dir_fds(opts.pid)
    old_dir_fds = tuple(old_dir_fds)

    #reopen dirfds
    for fileno, path in old_dir_fds:
        O_DIRECTORY = 00200000
        # get path to new version of file
        newpath = os.path.join(opts.root, path.lstrip('/'))
        # translate new path to inside chroot
        relpath = os.path.join('/', newpath[len(old_root):])
        newfd = run_gdb_cmd_in_pid('output open(%s, %#o)' %
                                   (json.dumps(relpath), O_DIRECTORY),
                                   opts.pid)
        if newfd < 0:
            raise Exception('Opening new dir fd failed')
        dupres = run_gdb_cmd_in_pid('output dup2(%d, %d)' % (newfd, fileno),
                                    opts.pid)
        if dupres < 0:
            raise Exception('Replacing dir fd failed')
        closeres = run_gdb_cmd_in_pid('output close(%d)' % newfd, opts.pid)
        if closeres < 0:
            warnings.warn('Failed to close new dir fd %s' % newfd)

    #chroot
    if old_root != opts.root:
        relative_root = os.path.join('/', os.path.relpath(opts.root, old_root))
        res = run_gdb_cmd_in_pid('output chroot(%s)' %
                                 json.dumps(relative_root), opts.pid)
        if res != 0:
            raise Exception('chroot failed')

    #chdir
    relative_cwd = os.path.join('/', os.path.relpath(old_cwd, old_root))
    res = run_gdb_cmd_in_pid('output chdir(%s)' %
                             json.dumps(relative_cwd), opts.pid)


if __name__ == '__main__':
    run()
