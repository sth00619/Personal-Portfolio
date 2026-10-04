#!/usr/bin/env bash
set -euo pipefail

data_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
data_file="${data_dir}/LC_loans_granting_model_dataset.csv"
data_url="https://zenodo.org/api/records/11295916/files/LC_loans_granting_model_dataset.csv/content"
expected_md5="b019384d6bc65bf2a3e839362e4ff502"

curl --fail --location --retry 3 --output "${data_file}.part" "${data_url}"
if command -v md5sum >/dev/null 2>&1; then
  actual_md5="$(md5sum "${data_file}.part" | cut -d ' ' -f 1)"
else
  actual_md5="$(md5 -q "${data_file}.part")"
fi
if [[ "${actual_md5}" != "${expected_md5}" ]]; then
  echo "Checksum mismatch: ${actual_md5}" >&2
  exit 1
fi
mv "${data_file}.part" "${data_file}"
echo "Downloaded ${data_file}"
