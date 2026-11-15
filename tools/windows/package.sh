#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
destination=${1:?Supply a new staging directory}
mkdir -- "$destination"
mkdir -- "$destination/bin" "$destination/sql" "$destination/client" "$destination/licenses"

executables=(bin/server.exe bin/bigbang.exe)
argon2=/usr/bin/cygargon2-1.dll
cp -- "${executables[@]}" "$argon2" "$destination/bin/"

# cygcheck recursively lists imported DLLs. Include the Argon2 DLL explicitly
# because the server opens it at runtime.
dependencies=$(cygcheck "${executables[@]}" "$argon2")
while IFS= read -r line; do
    path=${line#"${line%%[![:space:]]*}"}
    path=${path%$'\r'}
    [[ ${path,,} == *.dll ]] || continue
    unix_path=$(cygpath -u "$path")
    if [[ "$unix_path" -ef "/usr/bin/${unix_path##*/}" ]]; then
        cp -- "$unix_path" "$destination/bin/"
    fi
done <<< "$dependencies"
test -f "$destination/bin/cygwin1.dll"
test -f "$destination/bin/cygpq-5.dll"

cp -R -- sql/pg "$destination/sql/"
cp -- client/python_client/*.py client/python_client/menus.json "$destination/client/"
cp -- tools/windows/{Initialize-Universe.ps1,Start-Server.ps1,bigbang.example.json} "$destination/"
cp -- tools/windows/README.md "$destination/README.md"
cp -- COPYING LICENSE "$destination/licenses/"
cp -R -- /usr/share/doc/Cygwin "$destination/licenses/"
git rev-parse HEAD > "$destination/source-commit.txt"
