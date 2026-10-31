#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/.." && pwd)"
widget_python="${AI_LIMITS_BUILD_PYTHON:-python3}"
version="${1:-}"

if ! command -v "$widget_python" >/dev/null 2>&1; then
  echo "Python 3 não foi encontrado." >&2
  exit 1
fi

if [[ -z "$version" ]]; then
  version="$($widget_python -c 'import pathlib, sys, tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["project"]["version"])' "$project_root/pyproject.toml")"
fi
if [[ ! "$version" =~ ^[0-9]+([.][0-9]+){1,3}([+~-][0-9A-Za-z.+~-]+)?$ ]]; then
  echo "Versão inválida para o pacote Debian: $version" >&2
  exit 1
fi

for required_command in dpkg dpkg-deb install sha256sum; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    echo "Comando obrigatório não encontrado: $required_command" >&2
    exit 1
  fi
done
if ! "$widget_python" -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller não encontrado. Execute: python3 -m pip install -r requirements-build.txt" >&2
  exit 1
fi

architecture="$(dpkg --print-architecture)"
build_root="$project_root/build/linux"
dist_path="$build_root/dist"
work_path="$build_root/work"
spec_path="$build_root/spec"
package_root="$build_root/package-root"
app_name="ai-limits-widget"
bridge_name="ai-limits-agy-bridge"
app_path="$dist_path/$app_name"

if [[ "$build_root" != "$project_root/build/linux" ]]; then
  echo "Diretório de build inesperado: $build_root" >&2
  exit 1
fi
rm -rf -- "$build_root"
mkdir -p "$dist_path" "$work_path" "$spec_path"

"$widget_python" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$app_name" \
  --paths "$project_root/src" \
  --collect-submodules ai_limits_widget \
  --distpath "$dist_path" \
  --workpath "$work_path/app" \
  --specpath "$spec_path" \
  "$project_root/packaging/frozen_launcher.py"

"$widget_python" -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --console \
  --name "$bridge_name" \
  --paths "$project_root/src" \
  --hidden-import ai_limits_widget.platform_support \
  --distpath "$app_path" \
  --workpath "$work_path/agy-bridge" \
  --specpath "$spec_path" \
  "$project_root/src/ai_limits_widget/agy_bridge.py"

if [[ ! -x "$app_path/$app_name" || ! -x "$app_path/$bridge_name" ]]; then
  echo "Os executáveis esperados não foram gerados em $app_path." >&2
  exit 1
fi

install -d \
  "$package_root/DEBIAN" \
  "$package_root/usr/bin" \
  "$package_root/usr/lib/$app_name" \
  "$package_root/usr/share/applications" \
  "$package_root/usr/share/doc/$app_name"
cp -a "$app_path/." "$package_root/usr/lib/$app_name/"
ln -s "/usr/lib/$app_name/$app_name" "$package_root/usr/bin/$app_name"
install -m 0644 "$project_root/packaging/linux/ai-limits-widget.desktop" \
  "$package_root/usr/share/applications/ai-limits-widget.desktop"
install -m 0644 "$project_root/LICENSE" "$package_root/usr/share/doc/$app_name/copyright"
install -m 0644 "$project_root/NOTICE" "$project_root/THIRD_PARTY_NOTICES.md" \
  "$package_root/usr/share/doc/$app_name/"

installed_size="$(du -sk "$package_root/usr" | cut -f1)"
sed \
  -e "s|@VERSION@|$version|g" \
  -e "s|@ARCHITECTURE@|$architecture|g" \
  -e "s|@INSTALLED_SIZE@|$installed_size|g" \
  "$project_root/packaging/linux/control.in" > "$package_root/DEBIAN/control"
chmod 0644 "$package_root/DEBIAN/control"

deb_file="$build_root/${app_name}_${version}_${architecture}.deb"
dpkg-deb --root-owner-group --build "$package_root" "$deb_file"
dpkg-deb --info "$deb_file" >/dev/null
dpkg-deb --contents "$deb_file" >/dev/null

hash_file="$deb_file.sha256"
(
  cd -- "$build_root"
  sha256sum "$(basename -- "$deb_file")" > "$(basename -- "$hash_file")"
)

echo "Pacote Ubuntu gerado com sucesso."
echo "Arquivo: $deb_file"
echo "Checksum: $hash_file"
