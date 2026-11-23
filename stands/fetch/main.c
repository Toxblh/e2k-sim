/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdio.h>
#include <stdlib.h>
long stand(long iters);
int main(int c, char **v) { long n = atol(v[1]); printf("%ld\n", stand(n)); return 0; }
