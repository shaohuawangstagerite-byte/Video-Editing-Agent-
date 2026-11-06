#!/usr/bin/env bash
if ! command -v python >/dev/null 2>&1; then
    printf 'FAIL [依赖] 路径=%s: 缺少 Python 3，请确保 python 在 PATH 中\n' "${1:-<未提供>}" >&2
    exit 2
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 2
exec python -X utf8 "$script_dir/validate.py" "$@"
