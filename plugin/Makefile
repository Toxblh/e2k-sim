# SPDX-License-Identifier: GPL-2.0-or-later
# Build the qemu plugins against a qemu-e2k source tree (see ../qemu/README.md).
#   make QEMU_SRC=/path/to/qemu-e2k
QEMU_SRC ?= ../../qemu-e2k
CC ?= gcc
CFLAGS ?= -O2 -g -Wall
GLIB_CFLAGS := $(shell pkg-config --cflags glib-2.0)

all: libetrace.so libregs.so

lib%.so: %.c
	$(CC) $(CFLAGS) -shared -fPIC -I$(QEMU_SRC)/include/qemu $(GLIB_CFLAGS) -o $@ $<

clean:
	rm -f libetrace.so libregs.so

.PHONY: all clean
