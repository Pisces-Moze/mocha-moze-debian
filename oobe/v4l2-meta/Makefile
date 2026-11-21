# SPDX-License-Identifier: LGPL-2.1-or-later
CC ?= cc
PKG_CONFIG ?= pkg-config
PKGS = gstreamer-1.0 gstreamer-video-1.0
PLUGIN = libgstv4l2metabridge.so

$(PLUGIN): gstv4l2metabridge.c
	$(CC) -shared -fPIC -O2 -Wall -Wextra -Wl,-z,relro,-z,now \
	  -Wl,-soname,$(PLUGIN) -o $@ $< \
	  $(shell $(PKG_CONFIG) --cflags --libs $(PKGS))

install: $(PLUGIN)
	install -D -m 0644 $(PLUGIN) $(DESTDIR)/usr/local/lib/mocha-oobe/gstreamer-1.0/$(PLUGIN)

.PHONY: install
