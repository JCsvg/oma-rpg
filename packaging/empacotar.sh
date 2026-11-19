#!/usr/bin/env bash
# Gera o tarball a partir do git e constrói o pacote com makepkg (igual ao do oma-spotify).
#
#   packaging/empacotar.sh            constrói (e roda namcap, se existir)
#   packaging/empacotar.sh -d         constrói sem conferir dependências (makepkg -d)
#   packaging/empacotar.sh --install  constrói e instala com pacman -U
#
# Tudo acontece dentro de packaging/. O tarball sai do último commit: faça commit antes.
set -euo pipefail

aqui=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
raiz=$(cd "$aqui/.." && pwd)
pkgver=$(sed -n 's/^pkgver=//p' "$aqui/PKGBUILD")
nome="oma-rpg-$pkgver"
tarball="$aqui/$nome.tar.gz"

git -C "$raiz" archive --format=tar --prefix="$nome/" HEAD | gzip -n >"$tarball"
echo "tarball: $tarball"
echo "sha256:  $(sha256sum "$tarball" | cut -d' ' -f1)"

cd "$aqui"
rm -rf src pkg
makepkg -f --cleanbuild "$@"

if command -v namcap >/dev/null; then
  echo "--- namcap"
  namcap PKGBUILD || true
  namcap "$aqui"/oma-rpg-"$pkgver"-*.pkg.tar.* || true
fi
