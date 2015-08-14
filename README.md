Live atomic updates
===================

The problem
-----------

### Why atomic updates?

We love our precious uptime, so it's nice when we can apply updates while
the system is live.

We can do individual file updates by writing the new version of the file to a temporary file,
then use [rename(2)][] to atomically replace the dentry with the new version.

This alone is not sufficient for a safe update as:
1.  Unless your system is built of monolithic binaries (I'm looking at you Go),
    you will have files that depend on each other.
2.  If writing the new version of a file mid-update fails,
    then it can be very difficult to roll back to the previous state.

So the ways to solve this are:

1.  Design your software stack such that there is always a safe update sequence
    and declare this in metadata so on package update you can calculate
    a safe total update sequence for the whole software stack.

    I think NixOS gets this by installing everything to explicitly versioned paths,
    and configures software to look for its dependencies by these versioned paths,
    then symlinks entry points into the default search paths for user applications.

    This requires patching through most of the stack for it to work right.

2.  *Shut down everything* while doing a software update,
    so there's no chance of a running service starting something
    while the update is in progress,
    and failing unexpectedly.

    [SystemUpdates][] provides this way if you `systemctl isolate system-update.target`
    and allows a btrfs snapshot to allow rollback if package install fails.

    While this is more reliable than normal package installation,
    it only gives the illusion of uptime,
    as you've only avoided restarting the kernel.
    You've still had to shut down all your services.

3.  Separate all your application services out into containers,
    leaving only a small core,
    only responsible for managing the containers,
    which hopefully doesn't need to be updated very often.

    This is the model [CoreOS][] and [Project Atomic][] use.

    This allows easy atomic update of applications
    by passing the state over into the new version of the application.

    This is not a full solution though,
    as the core will need to be updated periodically,
    and while both [CoreOS][] and [Project Atomic][] support atomic updates of the host,
    they only do so with a reboot.

So how do we solve the Live atomic update problem?
--------------------------------------------------

Inspiration for this comes from the boot process,
where we migrate from running in the initramfs to the real root.

This is usually handled by either a [pivot_root(8)][] or [switch_root(8)][],
and if you can construct a mount tree that mirrors that of the original,
except that it has different versions of the software,
then you can pivot to that root and unmount the old root,
at which point you now have a root with the new versions.

The running services prevent unmounting of the old root mounts,
so you need to either:

1.  Ensure that the services are in their own mount namespaces,
    so unmounting it in your namespace won't affect the other processes.
2.  Detach the mounts (TODO: does this leave the old tree accessible to processes rooted in it).
3.  Restart all other services immediately, rather than on-demand.

Eventually all the services that relied on the old mount should be restarted,
so that the snapshot they use can be cleaned up.

How is restarting services after pivoting init's root better than shutting them down before pivoting and starting them again after?
-----------------------------------------------------------------------------------------------------------------------------------

Currently you could do the pivot,
but it shuts down all the processes,
even ones which could perfectly happily continue as-is,
like containers which don't use anything from the host's filesystem.

These containers could be left running during the pivot,
and won't need updating after it has completed.

Services not running in containers *do* need updating,
but they should be able to cope with init being in a different mount tree,
so init can be updated independently,
so when these services need to be updated,
they *can* be restarted instead of stopped and started again,
which allows graceful hand-over of state to the successor service,
which can work without causing service outage.

Ok, what have you got?
----------------------

Patches to systemd to add a command to make it pivot without killing all processes.

A script for duplicating the mount tree with modifications,
so that you have something to instruct systemd to pivot into.

Detaching the old root, before restarting old services.

Usage
-----

### migratelib

This tool works by allowing you to replace a mounted filesystem, so if your
root filesystem is versioned as each version has a different btrfs subvolume,
then you can change software versions by mounting a different subvolume.

In Baserock, this works by mounting the `/systems/$VERSION/run` subvolume as /.

#### The `--replace` option

Each mount replacement is started with `--replace`, with the options for each
replacement afterwards, until the next `--replace` option.

#### The `--filter` option

`--filter MATCH... [--filter MATCH...]...` takes key-value pairs of options, as
produced by the `findmnt --pairs` command. Multiple pairs can be given per
`--filter` option, and multiple `--filter` options can be given.

Typically the match `TARGET=$PATH` is sufficient, but if there are multiple
overlaid mounts, then more specific filters are required, as if there's
multiple matching mounts, then the first is chosen and a warning is emitted.

#### Replacement mount options

The `--mount-source` option specifies a device when mounting a disk, a
directory when bind-mounting, or is ignored for special types of filesystems.

The `--mount-type` option specifies the type of fileysystem, this is optional,
but faster, for disk mounts, ignored for bind mounts and required for special
filesystem mounts.

The `-o` or `--mount-options` option specifies mount options to pass to the
mount command. Multiple options can be given to the same option as either
separate arguments or comma separated values, and the option can be specified
multiple times.

So, for a Baserock system to change the version of its rootfs to `$VERSION`, we
can run this command:

    new_root="$(python -m migratelib.mount_tree -- \
        --replace --filter TARGET=/ \
                  --mount-source /dev/sda -o subvol=/systems/"$VERSION"/run)"

### pivoting with systemd

The current version has a d-bus interface that can be interacted with using:

    systemctl upgrade-root "$new_root"

After this, you are using the new systemd with all the old services,
and they can be updated on-demand to use the new versions.

You will need to reload the getty or sshd service and log back in to see the new fs tree.

<!-- TODO: Add instructions for reloading everything necessary -->

### Cleaning up old mounts

The old root is still available at `/mnt`.
If all the services from the old root have been restarted,
it should be possible to recursively unmount it,
if not you can detach it.

What's missing
--------------

0.  Any indication that my idea has merit and should be merged upstream.

1.  If PID1 exec fails after the point of no return, system hosed,
    You get an unignorable sigsegv,
    and you don't have enough of a process left to do anything with it.

    This isn't a new problem, `systemctl daemon-reexec` is also suceptible,
    but both are problematic for live updates.

    It's rare that this could happen,
    requiring either that something is fiddling with the page mappings between the kernel's back,
    or that the executable is being modified while it is being executed,
    which is difficult, given exec fails if a binary is open for writing,
    and opening for writing fails if it is busy execing the binary.

    Would be nice if we could hand-over the root reaper process responsibility,
    then you could have an A/B failover.

    Otherwise it would be nice to have some process pivot functionality.

2.  The process requesting the pivot could potentially have a different view
    to that of init.

    Perhaps a (dirfd, dirname) pair should be sent rather than a file path.

    Perhaps it should be given a namespace fd to enter,
    since it ought to be in a different namespace anyway
    if there are other services using the old one.

    Perhaps init should be told what modifications need to be made to its mount tree instead.

3.  Constructing the new mount tree based on the existing one with changes
    then instructing init to enter it is racy,
    as something could mount something in the meantime.

    Using `rbind` rather than `bind` would reduce that risk to just mounts on top of the mounts we want to replace,
    and doing the move in a namespace with slave mount propagation
    means we can mount the new tree without other namespaces seeing it.

    However this doesn't remove the risk of there being a mount on top of the mounts we want to replace,
    between our new tree being created and starting to use it.

    We could either enforce more rigid separation between services,
    by requiring that they all have private or slave mount propagation;
    Or we could prevent them being able to perform mounts in that interval,
    by suspending all processes with the freezer cgroup.

    None of these are ideal, so more ideas would be better.

[rename(2)]: http://man7.org/linux/man-pages/man2/rename.2.html
[SystemUpdates]: http://freedesktop.org/wiki/Software/systemd/SystemUpdates/
[CoreOS]: https://coreos.com/
[Project Atomic]: http://www.projectatomic.io/
[pivot_root(8)]: http://man7.org/linux/man-pages/man8/pivot_root.8.html
[switch_root(8)]: http://man7.org/linux/man-pages/man8/switch_root.8.html
