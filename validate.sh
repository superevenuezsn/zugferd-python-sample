#!/usr/bin/env bash
# Validate every generated e-invoice with Mustangproject (EN 16931 rules + PDF/A-3 check).
# Download the CLI once:  https://github.com/ZUGFeRD/mustangproject/releases  (Mustang-CLI-*.jar)
set -euo pipefail
JAR="${MUSTANG_JAR:-tools/Mustang-CLI.jar}"
mkdir -p reports
status=0
for f in output/*.pdf; do
  n=$(basename "$f" .pdf)
  java -jar "$JAR" --no-notices --action validate --source "$f" > "reports/$n.xml" 2>/dev/null || true
  if grep -q '<summary status="invalid"/>' "reports/$n.xml"; then
    echo "INVALID  $n  (see reports/$n.xml)"; status=1
  else
    echo "VALID    $n"
  fi
done
exit $status
