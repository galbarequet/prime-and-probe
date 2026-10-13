UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
CC = clang
LDLIBS = -lpthread
else
CC = gcc
endif

ifeq ($(DEBUG),1)
CFLAGS = -g -Wall -Wextra -std=c11
else
CFLAGS = -O2 -Wall -Wextra -std=c11
endif

# Target the efficiency cluster by default (cleaner prime+probe heatmap on Apple
# Silicon). Build the performance-core variant with `make pp EFFICIENCY_CORE=0`.
EFFICIENCY_CORE ?= 1
ifeq ($(EFFICIENCY_CORE),1)
CFLAGS += -DUSE_EFFICIENCY_CORE
endif

.PHONY: all clean

all: pp aes_pp

pp: pp.c victim.c run_pp.c pointer_chasing.c cpu_affinity.c arch_primitives.c
	$(CC) $(CFLAGS) -o pp pp.c victim.c run_pp.c pointer_chasing.c cpu_affinity.c arch_primitives.c $(LDLIBS)

aes_pp: aes_pp.c pp.c victim.c pointer_chasing.c aes_utils.c AES/aes_core.c cpu_affinity.c arch_primitives.c
	$(CC) $(CFLAGS) -o aes_pp aes_pp.c pp.c victim.c pointer_chasing.c aes_utils.c AES/aes_core.c cpu_affinity.c arch_primitives.c $(LDLIBS)

clean:
	rm -f pp aes_pp
