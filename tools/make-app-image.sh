#!/bin/bash
set -euo pipefail
root=$(realpath "${1:?rootfs}");out=$(realpath -m "${2:?APP image}");bytes=${3:?exact APP partition bytes}
test "$EUID" = 0;test ! -e "$out";test -f "$root/boot/initramfs.cpio.gz"
case "$bytes" in *[!0-9]*|'')exit 2;;esac
mkdir -p "$(dirname "$out")"
truncate -s "$bytes" "$out"
# Populate through libext2fs; no loop device or CAP_SYS_ADMIN is required.
# mke2fs -d preserves ownership, hard links and xattrs from the staging tree.
mkfs.ext4 -F -L mocha-debian -O '^64bit,^metadata_csum,^orphan_file' -d "$root" "$out"
e2fsck -fn "$out"
sha256sum "$out" > "$out.sha256"
