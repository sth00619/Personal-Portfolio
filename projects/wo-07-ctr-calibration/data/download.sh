#!/usr/bin/env bash
set -euo pipefail

data_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
base_url="https://huggingface.co/datasets/criteo/CriteoClickLogs/resolve/main/data"

download() {
  local day="$1"
  local part="$2"
  local expected_sha256="$3"
  local target="$data_dir/${day}.parquet"
  if [[ -s "$target" ]]; then
    if [[ "$(shasum -a 256 "$target" | cut -d ' ' -f 1)" == "$expected_sha256" ]]; then
      printf 'Already verified: %s\n' "$target"
      return
    fi
    printf 'Checksum mismatch: %s\n' "$target" >&2
    exit 1
  fi
  curl --fail --location --retry 3 --silent --show-error --output "${target}.tmp" "${base_url}/day=${day}/${part}"
  if [[ "$(shasum -a 256 "${target}.tmp" | cut -d ' ' -f 1)" != "$expected_sha256" ]]; then
    printf 'Checksum mismatch after download: %s\n' "$target" >&2
    exit 1
  fi
  mv "${target}.tmp" "$target"
  printf 'Downloaded: %s\n' "$target"
}

download '2015-02-15' 'part-03358-99c339d5-fbac-4110-9dcf-75453a61a5c1.c000.snappy.parquet' 'c99c772478979160b28b94692ff6f45b32fb3511c6de9dda7607096c2075f91d'
download '2015-02-16' 'part-04127-99c339d5-fbac-4110-9dcf-75453a61a5c1.c000.snappy.parquet' 'fa2086237e6f0d1e2085bbe0dd526806ac61853aab4f0c5a06468675cf8d4401'
download '2015-02-17' 'part-01473-99c339d5-fbac-4110-9dcf-75453a61a5c1.c000.snappy.parquet' '0d8aaa25a4c412ce030dc889d2d853ec0f4128cc435af01819bea015f90cd08c'
download '2015-02-18' 'part-00677-99c339d5-fbac-4110-9dcf-75453a61a5c1.c000.snappy.parquet' 'f082372f26c0f34063c8989bcc47b279d58b0215bcc1fdb0f252accf25dbbdfb'
