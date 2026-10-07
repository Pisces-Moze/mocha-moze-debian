#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Run only inside the key-authorized RAM installer. APP/LNX only; no GPT edit.
set -eu
die() { echo "$*" >&2;exit 1; }
test "$(cat /proc/1/comm)" = init || die 'RAM installer PID1 required'
test -b /dev/mmcblk0 || die 'No eMMC'
awk '$1 ~ /^\/dev\/mmcblk0/ { found=1 } END { exit found ? 0 : 1 }' /proc/mounts && die 'eMMC mounted'
case "${1:-}" in
plan)
 test "$(blockdev --getro /dev/mmcblk0)" = 1 || die 'Disk must be read-only'
 printf 'CID=%s\n' "$(cat /sys/class/block/mmcblk0/device/cid)"
 printf 'DISK_SECTORS=%s\n' "$(cat /sys/class/block/mmcblk0/size)"
 for spec in APP:26 LNX:22;do
  label=${spec%:*};num=${spec#*:}
  printf '%s_START=%s\n' "$label" "$(cat /sys/class/block/mmcblk0p$num/start)"
  printf '%s_SECTORS=%s\n' "$label" "$(cat /sys/class/block/mmcblk0p$num/size)"
 done
 ;;
write)
 label=${2:?APP or LNX};image=${3:?image};plan=${4:?layout.env};confirm=${5:?explicit replacement token}
 case "$label" in APP)num=26;;LNX)num=22;;*)die 'APP/LNX only';;esac
 test "$confirm" = "REPLACE_$label" || die 'Wrong replacement token'
 get() { awk -F= -v key="$1" '$1==key { print $2; n++ } END {if(n!=1)exit 1}' "$plan"; }
 test "$(get CID)" = "$(cat /sys/class/block/mmcblk0/device/cid)" || die 'Device CID changed'
 test "$(get DISK_SECTORS)" = "$(cat /sys/class/block/mmcblk0/size)" || die 'Disk size changed'
 test "$(get "${label}_START")" = "$(cat /sys/class/block/mmcblk0p$num/start)" || die 'Partition start changed'
 sectors=$(get "${label}_SECTORS")
 test "$sectors" = "$(cat /sys/class/block/mmcblk0p$num/size)" || die 'Partition size changed'
 # This snapshot supports only the stock 16 GB APP/LNX layout.
 if [ "$label" = APP ];then test "$(get APP_START):$sectors" = 524288:2612431 || die 'Unsupported APP layout';else test "$(get LNX_START):$sectors" = 393216:40960 || die 'Unsupported LNX layout';fi
 bytes=$(wc -c < "$image" | tr -d ' ');capacity=$((sectors*512))
 test "$bytes" -gt 0 && test "$bytes" -le "$capacity" || die 'Image size invalid'
 if [ "$label" = APP ];then test "$bytes" = "$capacity" || die 'APP image must match full partition';fi
 expected=$(sha256sum "$image" | awk '{print $1}')
 dev=/dev/mmcblk0p$num
 restore() { blockdev --setro "$dev";blockdev --setro /dev/mmcblk0; }
 trap restore EXIT HUP INT TERM
 blockdev --setrw /dev/mmcblk0;blockdev --setrw "$dev"
 dd if="$image" of="$dev" bs=1048576 conv=fsync
 sync;restore
 actual=$(head -c "$bytes" "$dev" | sha256sum | awk '{print $1}')
 test "$actual" = "$expected" || die 'Readback SHA256 mismatch'
 echo "$label written and readback verified: $actual"
 ;;
*)die 'Use: storage.sh plan OR storage.sh write APP|LNX IMAGE layout.env REPLACE_APP|REPLACE_LNX';;
esac
