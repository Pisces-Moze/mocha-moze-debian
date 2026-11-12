#!/bin/bash
set -euo pipefail
root=$(realpath -m "${1:?rootfs output}");key=$(realpath "${2:?authorized public key}");kernel=$(realpath "${3:?kernel output}")
repo=$(cd "$(dirname "$0")/.." && pwd)
test "$EUID" = 0;test ! -e "$root";grep -Eq '^ssh-(ed25519|rsa) ' "$key"
mirror=${MOCHA_DEBIAN_MIRROR:-https://mirrors.aliyun.com/debian}
debootstrap --foreign --arch=armhf --variant=minbase --include=systemd-sysv,openssh-server,dropbear-bin,busybox-static,kmod,udev,iproute2,iputils-ping,ca-certificates,network-manager,sudo trixie "$root" "$mirror"
install -m755 /usr/bin/qemu-arm-static "$root/usr/bin/qemu-arm-static"
chroot "$root" /debootstrap/debootstrap --second-stage
mount --bind /dev "$root/dev";mount -t proc proc "$root/proc";mount -t sysfs sysfs "$root/sys"
trap 'umount "$root/sys" "$root/proc" "$root/dev"' EXIT
printf 'mocha\n' > "$root/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 mocha\n' > "$root/etc/hosts"
printf 'LABEL=mocha-debian / ext4 defaults 0 1\n' > "$root/etc/fstab"
touch "$root/etc/mocha-internal-debian"
chroot "$root" useradd -m -s /bin/bash mocha
chroot "$root" usermod -aG sudo mocha
# This is the documented local default for the prototype image; the offline
# distribution stage resets it and removes the temporary administrator key.
printf 'mocha:mocha\n' | chroot "$root" chpasswd
install -d -m700 "$root/root/.ssh"
install -m600 "$key" "$root/root/.ssh/authorized_keys"
install -d "$root/etc/ssh/sshd_config.d"
printf 'PermitRootLogin prohibit-password\nPasswordAuthentication no\n' > "$root/etc/ssh/sshd_config.d/mocha.conf"
# Fresh keys belong to this installation, never to the maintainer tablet.
chroot "$root" ssh-keygen -A
install -d "$root/boot" "$root/usr/local/libexec" "$root/etc/systemd/system"
cp "$kernel/uImage" "$root/boot/uImage-desktop"
cp "$kernel/mocha.dtb" "$root/boot/mocha-desktop.dtb"
cp -a "$kernel/modules/lib/modules" "$root/usr/lib/"
mapfile -t releases < <(find "$root/usr/lib/modules" -mindepth 1 -maxdepth 1 -type d -printf '%f\n')
test "${#releases[@]}" = 1
release=${releases[0]}
test -n "$release";test -d "$kernel/modules/lib/modules/$release"
chroot "$root" depmod "$release"
install -m755 "$repo/rootfs/mocha-usb" "$root/usr/local/libexec/mocha-usb"
cp "$repo/rootfs/mocha-usb.service" "$root/etc/systemd/system/"
chroot "$root" systemctl enable ssh.service mocha-usb.service NetworkManager.service
chroot "$root" apt-get clean
rm -f "$root/usr/bin/qemu-arm-static"
echo 'Core rootfs ready. Firmware, final initramfs, backlight module and desktop remain separate steps.'
