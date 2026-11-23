/* SPDX-License-Identifier: GPL-2.0-or-later */
/* regs: debug plugin, prints the register names qemu-e2k exposes to plugins (qemu_plugin_get_registers). */
#include <glib.h>
#include <stdio.h>
#include <qemu-plugin.h>
QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;
static void vinit(qemu_plugin_id_t id, unsigned int vcpu) {
  GArray *r = qemu_plugin_get_registers();
  fprintf(stderr, "nregs %u:", r->len);
  for (guint i = 0; i < r->len && i < 600; i++) fprintf(stderr, " %s", g_array_index(r, qemu_plugin_reg_descriptor, i).name);
  fprintf(stderr, "\n");
}
QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id, const qemu_info_t *info, int argc, char **argv) {
  qemu_plugin_register_vcpu_init_cb(id, vinit); return 0;
}
