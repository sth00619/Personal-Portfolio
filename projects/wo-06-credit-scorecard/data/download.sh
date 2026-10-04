#!/usr/bin/env bash
set -euo pipefail

data_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
data_file="${data_dir}/LC_loans_granting_model_dataset.csv"
data_url="https://zenodo.org/api/records/11295916/files/LC_loans_granting_model_dataset.csv/content"
expected_md5="b019384d6bc65bf2a3e839362e4ff502"

checksum() {
  if command -v md5sum >/dev/null 2>&1; then
    md5sum "$1" | cut -d ' ' -f 1
  else
    md5 -q "$1"
  fi
}

if [[ -f "${data_file}" ]] && [[ "$(checksum "${data_file}")" == "${expected_md5}" ]]; then
  echo "Verified existing ${data_file}"
  exit 0
fi

curl --fail --location --retry 3 --output "${data_file}.part" "${data_url}"
actual_md5="$(checksum "${data_file}.part")"
if [[ "${actual_md5}" != "${expected_md5}" ]]; then
  echo "Checksum mismatch: ${actual_md5}" >&2
  exit 1
fi
mv "${data_file}.part" "${data_file}"
echo "Downloaded ${data_file}"
