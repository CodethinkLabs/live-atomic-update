Online atomic updates
=====================

The problem
-----------

Current solutions for atomic replacement of components require a reboot to
apply, which can cause unacceptably long outages for high performance hardware
that takes tens of minutes to boot.

The updates must be atomic because we want to go from the old state to the new
state with no transition states in-between.

We're not alone in doing image-based systems, see ostree and project atomic.

This is because package based systems can handle this by defining a safe order
for replacement of individual files, which varies between versions, introduces
extra responsibilities for package maintainers, and the steps to make this safe
make update application slow.

Atomicity is good, as it allows you to make guarantees about what's contained
in the filesystem at any given time.

However, Linux currently lacks mechanisms for swapping between atomic updates
without a service interruption.

A proposed solution
-------------------

ptrace is a system call used for debugging. One of its features is that
you can use it to inject code, which is traditionally used to inject
breakpoints and print or modify state.

We can switch to a new version of the system by mounting the new tree and
pivoting into it, but existing processes will continue to use the original
version until they are migrated.

To migrate processes into the new version of the mount tree, we will:

1.  Create a prallel mount tree with the system image's mount replaced
    with the new version.

2.  Use ptrace to enter the process and have them chroot, chdir and re-open any
    directory file descriptors.

3.  Use pivot_root to swap the mount trees around

4.  Lazily unmount (umount2(path, MNT_DETACH)) the mount points, so when
    processes close all files opened on the old mount tree, it is unmounted.

5.  Instruct services to gracefully re-exec as necessary

Services need to re-exec to stop using files from the old mount tree. This is
not unusual though, as package-based online updates also leave processes with
open files that are no longer reachable.

It would be possible to re-exec all services instead of attempting to migrate
them, but that would require patching the entire userland to be able to
gracefully re-exec.

Usage
-----

This tool works by allowing you to replace a mounted filesystem, so if your
root filesystem is versioned as each version has a different btrfs subvolume,
then you can change software versions by mounting a different subvolume.

In Baserock, this works by mounting the `/systems/$VERSION/run` subvolume as /.

### The `--replace` option

Each mount replacement is started with `--replace`, with the options for each
replacement afterwards, until the next `--replace` option.

### The `--filter` option

`--filter MATCH... [--filter MATCH...]...` takes key-value pairs of options, as
produced by the `findmnt --pairs` command. Multiple pairs can be given per
`--filter` option, and multiple `--filter` options can be given.

Typically the match `TARGET=$PATH` is sufficient, but if there are multiple
overlaid mounts, then more specific filters are required, as if there's
multiple matching mounts, then the first is chosen and a warning is emitted.

### Replacement mount options

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

    python -m migratelib.migrate_namespace -- \
        --replace --filter TARGET=/ \
                  --mount-source /dev/sda -o subvol=/systems/"$VERSION"/run

Limitations
-----------

1.  Can't migrate un-ptraceable processes.

    This includes anything currently being ptraced, anything that blocks
    ptracing and anything that is not ptraceable (such as kdevtmpfsd or
    other kworker processes).

2.  Can't migrate processes that have dropped the capability to chroot.

3.  Can't migrate processes that don't have the open, dup2, close, chroot or
    chdir syscall wrapper functions.

4.  Process migration is racy

    Processes may appear or disappear between scanning and migration.

    The directory file descriptors they have open may change between scanning
    and reopening.

5.  Unless gdb threads have their own thread-local errno, you can confuse
    processes if you migrate between a syscall being called and errno being
    checked, since syscalls will change errno.

6.  Any programs that rely on the output of stat on `/`, `.` or any opened
    directory fds can get confused, since they may change at migration time.

Future work to make this more reliable
--------------------------------------

1.  Freeze all processes before migrating

    Barring an atomic operation to migrate every process, every process needs
    to be frozen. This can be done with cgroups, but effectively requires that
    the process to drive migration is systemd, since you can't freeze the root
    cgroup.

2.  Add kernel support for this instead of using ptrace

    An enhanced pivot_root syscall that moves all processes in a namespace by
    changing their root, cwd and open directory fds would be ideal.

    ptrace is fundamentally unsuitable for this because syscalls are run with
    the target process' permissions, rather than the driver process, and not all
    processes can be ptraced.

    We can get away with syscalls for migrating another process' root, cwd and
    directory fds individually (such as making the entries in /proc modifiable
    with linkat) if we freeze all processes before migration.

3.  OR instead of migrating processes to a new mount tree, alter the mounted
    filesystem in a zero-copy manner.

    This still requires freezing all of userland except systemd unless we get a
    syscall to commit changes to a filesystem.

    If we don't need to copy data this shouldn't be slow, but it's a rename for
    each file in the intersection of both versions, a link for each file only
    in the new version, and an unlink for files not in the new version.

    A syscall for swapping the contents of a directory inode would make this
    quicker and easier, as you could build a map of the files open by processes,
    and swap entire subtrees when there's no open files in that subtree.

    This doesn't need anything filesystem specific to work, but rollback either
    requires it to either be a read-only hardlink tree (see ostree), or a CoW
    snapshot.

    This has the advantage of not needing to fiddle with a process' fds or
    mucking about with mount namespaces, and it doesn't break anything that was
    relying on the inode numbers to remain stable.


Alternative approaches
----------------------

The above may all be far too much work for online atomic updates to be a
reality, so some of the alternatives below may be preferable.

0.  Abandon atomic updates and have package updates.

    This means you can be in an inconsistent state if something goes wrong
    during a package update, and there's extra effort per-package to define safe
    ways of installing the new files while leaving the fs in a consistent state.

    This makes the amount of work required to maintain a distribution increase
    with the number of packages, so we want to avoid that for Baserock.

1.  Package applications as containers and update the whole container at once.

    This requires down-time per application, and it doesn't solve the problem
    with updating the base system if there's security problems in the container
    software.

2.  Kexec into the new system rather than a full reboot

    This reduces the down-time if hardware takes a long time to reboot, but it
    still has a service interruption.

    Not all hardware is kexec safe.

3.  Snapshot and restore processes with CRIU.

    This doesn't have a service interruption, but migrating processes with
    snapshot + restore is slow, and not all processes are snapshottable.

    It also may not be safe to restore in a different mount tree to that which
    it left.

4.  Have systemd pivot and re-exec all services

    This would either need to tear down and restart all services, causing a
    service interruption, or ask all services to gracefully re-exec, which
    requires patching the whole of the userland.
