#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Add signed Debian ARMhf maintenance tools, then remove all embedded keys.
set -euo pipefail
test "$EUID" = 0
input=$(realpath "${1:?verified maintenance cpio.gz}")
work=$(realpath -m "${2:?new private work directory}")
output=$(realpath -m "${3:?new installer cpio.gz}")
repo=$(cd "$(dirname "$0")/.." && pwd)
test ! -e "$work";test ! -e "$output"
mkdir -m700 -p "$work"/{root,apt/lists/partial,apt/archives/partial}
printf 'deb [arch=armhf signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://mirrors.aliyun.com/debian trixie main\n' > "$work/apt/sources.list"
options=(-o "Dir::Etc::sourcelist=$work/apt/sources.list" -o 'Dir::Etc::sourceparts=-'
 -o "Dir::State::lists=$work/apt/lists" -o APT::Architecture=armhf -o APT::Architectures=armhf
 -o Dir::State::status=/dev/null -o "Dir::Cache::archives=$work/apt/archives")
apt-get "${options[@]}" update
apt-get "${options[@]}" -y --download-only --no-install-recommends install python3 e2fsprogs fdisk tar xz-utils dropbear-bin
(cd "$work/root";gzip -dc "$input" | cpio --quiet -idmu)
for package in "$work/apt/archives"/*.deb;do dpkg-deb -x "$package" "$work/root";done
for binary in usr/bin/tar usr/bin/xz usr/bin/dropbearkey usr/bin/python3.13 usr/sbin/mkfs.ext4;do
 test -x "$work/root/$binary"
 arm-linux-gnueabihf-readelf -h "$work/root/$binary" | grep -q 'Machine:.*ARM'
done
(cd "$work/root";find . -print0 | cpio --null --quiet -o --format=newc --owner=0:0 | gzip -n -6 > "$work/augmented.cpio.gz")
python3 "$repo/tools/make-distribution-ram.py" "$work/augmented.cpio.gz" "$work/root/usr/bin/dropbearkey" "$output"
# Verify that the mandatory tools survived sanitization before distributing.
gzip -t "$output"
sha256sum "$output"
