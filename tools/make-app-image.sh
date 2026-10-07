#!/bin/bash
set -euo pipefail
root=$(realpath "${1:?rootfs}");out=$(realpath -m "${2:?APP image}");bytes=${3:?exact APP partition bytes}
test "$EUID" = 0;test ! -e "$out";test -f "$root/boot/initramfs.cpio.gz"
case "$bytes" in *[!0-9]*|'')exit 2;;esac
mkdir -p "$(dirname "$out")"
truncate -s "$bytes" "$out"
mkfs.ext4 -F -L mocha-debian -O '^64bit,^metadata_csum,^orphan_file' "$out"
mnt=$(mktemp -d);mount -o loop "$out" "$mnt"
trap 'umount "$mnt";rmdir "$mnt"' EXIT
rsync -aHAX --numeric-ids "$root/" "$mnt/"
sync
umount "$mnt";rmdir "$mnt";trap - EXIT
e2fsck -fn "$out"
sha256sum "$out" > "$out.sha256"
