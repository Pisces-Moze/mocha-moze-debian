#!/bin/sh
# Make request_module() use the same full module tree as modprobe -d.
set -eu
test "$(id -u)" = 0
version=$(uname -r)
tree=$(readlink -f "${1:?candidate module root, containing lib/modules}")
modules=$tree/lib/modules/$version
test -s "$modules/modules.dep"
mkdir -p /lib/modules
if [ ! -e "/lib/modules/$version" ] && [ ! -L "/lib/modules/$version" ]; then
    ln -s "$modules" "/lib/modules/$version"
fi
test "$(readlink -f "/lib/modules/$version")" = "$modules"
modprobe -d "$tree" brcmfmac
