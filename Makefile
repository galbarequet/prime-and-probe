UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
CC = clang
else
CC = gcc
endif

ifeq ($(DEBUG),1)
CFLAGS = -g -Wall -Wextra -std=c11
else
CFLAGS = -O2 -Wall -Wextra -std=c11
endif

.PHONY: all clean

all: pp aes_pp

pp: pp.c victim.c run_pp.c pointer_chasing.c
	$(CC) $(CFLAGS) -o pp pp.c victim.c run_pp.c pointer_chasing.c

aes_pp: aes_pp.c pp.c victim.c pointer_chasing.c aes_utils.c AES/aes_core.c
	$(CC) $(CFLAGS) -o aes_pp aes_pp.c pp.c victim.c pointer_chasing.c aes_utils.c AES/aes_core.c

clean:
	rm -f pp aes_pp
