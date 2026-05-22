#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PMARS_VERSION="0.9.4"
TARBALL="$ROOT/vendor/pmars_${PMARS_VERSION}.orig.tar.xz"
SRC="$ROOT/vendor/pmars-src"

mkdir -p "$ROOT/vendor"
if [[ ! -f "$TARBALL" ]]; then
  curl -L --fail "https://deb.debian.org/debian/pool/main/p/pmars/pmars_${PMARS_VERSION}.orig.tar.xz" -o "$TARBALL"
fi

env LC_ALL=C LANG=C shasum -a 256 "$TARBALL"
rm -rf "$SRC"
mkdir -p "$SRC"
tar -xf "$TARBALL" -C "$SRC" --strip-components=1
make -C "$SRC/src" clean
make -C "$SRC/src" CFLAGS='-std=gnu89 -Dround=pmars_round -O -DEXT94 -DPERMUTATE -DRWLIMIT -DSERVER' LIB='' LFLAGS=''
cp "$SRC/src/pmars" "$ROOT/vendor/pmars-bin"
env LC_ALL=C LANG=C "$ROOT/vendor/pmars-bin" -b -k -F 100 -r 10 "$SRC/warriors/aeka.red" "$SRC/warriors/rave.red"
