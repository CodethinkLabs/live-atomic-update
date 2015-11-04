#!/bin/sh
#
# Copyright (C) 2014-2015 Codethink Limited
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

# Recursive unmount, useful for testing as there's a lot of mounts to undo
set -eu

detach=false
if [ "$1" = -d ]; then
    detach=true
    shift
fi

findmnt -RrnoTARGET "$1" | tac | while read -r line; do
    if "$detach"; then
        umount -l "$(printf "$line")"
    else
        umount "$(printf "$line")"
    fi
done
