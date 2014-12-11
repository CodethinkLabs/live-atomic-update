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
from pipes import quote as shellescape
import re
import subprocess
import sys
import warnings


__all__ = ('get_pid_cwd', 'get_pid_root', 'git_pid_dir_fds',
           'run_gdb_cmd_in_pid', 'migrate_process')


# json.dumps is the closest thing to c string escapes
def cescape(s):
    assert isinstance(s, basestring)
    return json.dumps(s)


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

def _gdb_runner(args, **kwargs):
    return subprocess.check_output(['gdb'] + args, **kwargs)


def is_ptraceable(pid, runcmd=_gdb_runner):
    out = runcmd(['--pid', str(pid), '--batch'], stderr=subprocess.STDOUT)
    return 'ptrace: Operation not permitted.' not in out


def run_gdb_cmd_in_pid(command, pid, runcmd=_gdb_runner):
    argv = ['--quiet', '--pid', str(pid), '--batch',
            '--eval-command', 'output (int[2]){%s, errno}' % command]
    cmd_as_str = ' '.join(map(shellescape, argv))
    with open(os.devnull) as devnull:
        out = runcmd(argv, stderr=devnull)
    logging.debug('Running %s output %s' % (cmd_as_str, out))
    cmd_ret_out = out.splitlines()[-1].strip()
    outstrs = re.match(r'{([-\d]+), (\d+)}', cmd_ret_out)
    ecode = int(outstrs.group(1))
    errno = int(outstrs.group(2))
    logging.debug('Running %s returned %d with errno %d' %
                  (cmd_as_str, ecode, errno))
    return ecode, errno


def migrate_process(pid, new_root, gdbcmd=_gdb_runner):
    if not is_ptraceable(pid=pid, runcmd=gdbcmd):
	warnings.warn('Pid %d is not ptraceable' % pid)
	return
    old_root = get_pid_root(pid)
    if not new_root.startswith(old_root):
        raise Exception('New root not reachable from old root')

    old_cwd = get_pid_cwd(pid)
    old_dir_fds = get_pid_dir_fds(pid)
    old_dir_fds = tuple(old_dir_fds)

    #reopen dirfds
    for fileno, path in old_dir_fds:
        O_DIRECTORY = 0200000
        # get path to new version of file
        newpath = os.path.join(new_root, path.lstrip('/'))
        # translate new path to inside chroot
        relpath = os.path.join('/', newpath[len(old_root):])
        newfd, errno = run_gdb_cmd_in_pid('open(%s, %#o)' %
                                          (cescape(relpath), O_DIRECTORY),
                                          pid, runcmd=gdbcmd)
        if newfd < 0:
            raise Exception('Opening new dir fd failed: %s' %
                            os.strerror(errno))
        dupres = run_gdb_cmd_in_pid('dup2(%d, %d)' % (newfd, fileno),
                                    pid, runcmd=gdbcmd)
        if dupres < 0:
            raise Exception('Replacing dir fd failed: %s' %
                            os.strerror(errno))
        closeres = run_gdb_cmd_in_pid('close(%d)' % newfd, pid,
                                      runcmd=gdbcmd)
        if closeres < 0:
            warnings.warn('Failed to close new dir fd %s: %s' %
                          (newfd))

    #chroot
    if old_root != new_root:
        relative_root = os.path.join('/', os.path.relpath(new_root, old_root))
        res, errno = run_gdb_cmd_in_pid('chroot(%s)' %
                                        cescape(relative_root), pid)
        if res != 0:
            raise Exception('chroot failed')

    #chdir
    relative_cwd = os.path.join('/', os.path.relpath(old_cwd, old_root))
    res, errno = run_gdb_cmd_in_pid('chdir(%s)' %
                                    cescape(relative_cwd), pid)


def run():
    ap = create_arg_parser()
    opts = ap.parse_args()

    if opts.debug:
        logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    migrate_process(pid=opts.pid, new_root=opts.root)

if __name__ == '__main__':
    run()
