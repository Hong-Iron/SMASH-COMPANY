#!/bin/zsh
# Runs the data pipeline for every sub-area in areas.json (or the ones given): OSM + terrain, VWorld buildings + aerial,
# prep, SMASH data, page. Steps whose output exists are skipped, so a rerun only does what is missing.
# usage: zsh tools/build_all.sh [area …]
cd "${0:A:h}/.."
PY=~/.venvs/vault-plots/bin/python
areas=("$@")
[[ ${#areas} -eq 0 ]] && areas=($(python3 -c "import json;print(' '.join(json.load(open('areas.json'))))"))
for a in $areas; do
  echo "== $a"
  [[ -f raw/$a/osm.json ]] || python3 tools/fetch.py $a || { echo "fetch failed: $a"; continue; }
  [[ -f raw/$a/aerial.jpg ]] || $PY tools/vworld.py $a || { echo "vworld failed: $a"; continue; }
  $PY tools/prep_area.py $a && $PY tools/to_smash.py $a && python3 tools/assemble.py $a
done
