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


'Parse command-line arguments into rules for replacing mounts.'


import argparse
import itertools
flatten = itertools.chain.from_iterable


__all__ = ('extend_arg_parser',)


def extend_arg_parser(ap, argnames=('--replace',), dest='replace'):
    replaceparser = argparse.ArgumentParser()
    replaceparser.add_argument('--filter', nargs='*',
                               action='append', default=[])
    replaceparser.add_argument('--mount-source')
    replaceparser.add_argument('--mount-type')
    replaceparser.add_argument('--mount-options', '-o', nargs='*', action='append',
                               default=[])

    class RecursiveReplaceAction(argparse.Action):
        def __call__(self, subparser, subnamespace, values, option_string=None):
            subns, unparsed = replaceparser.parse_known_args(args=values)

            filters = frozenset(tuple(filter.split('=', 1))
                                for filter in sorted(flatten(subns.filter)))
            mount_options = tuple(flatten(subns.mount_options))

            replacements = getattr(subnamespace, self.dest)
            replacements[filters] = (subns.mount_source, subns.mount_type, mount_options)

            subnamespace._unrecognized_args = unparsed

    replaceparser.add_argument(*argnames, dest=dest, nargs=argparse.REMAINDER,
                               action=RecursiveReplaceAction, default={})

    class ToplevelReplaceAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            subns, unparsed = replaceparser.parse_known_args(args=values)

            filters = frozenset(tuple(filter.split('=', 1))
                                for filter in sorted(flatten(subns.filter)))
            mount_options = tuple(flatten(subns.mount_options))

            replacements = getattr(namespace, self.dest)
            replacements[filters] = (subns.mount_source, subns.mount_type, mount_options)
            parser.parse_args(args=unparsed, namespace=namespace)

    ap.add_argument(*argnames, dest=dest, nargs=argparse.REMAINDER,
                    action=ToplevelReplaceAction, default={})


def test():
    ap = argparse.ArgumentParser()
    extend_arg_parser(ap, argnames=('--rep', '-r'), dest='reps')
    ap.add_argument('--foo')
    ap.add_argument('bars', nargs='*', default=argparse.SUPPRESS)

    import shlex
    opts = ap.parse_args(shlex.split(r'''
        -r --filter TARGET=/ --mount-source /dev/vda --mount-type btrfs
           -o subvol=/systems/foo/run
        --rep --filter TARGET=/home --mount-source /dev/vda --mount-type btrfs
           -o subvol=/state/home
        --foo=bar
        a b 'c d'
    '''))

    assert opts.foo == 'bar'
    assert opts.bars == ['a', 'b', 'c d']


if __name__ == '__main__':
    test()
