#!/bin/bash
set -euo pipefail

WORKSPACE="/home/agent/autofinisher-factory"
REPORT_FILE="$WORKSPACE/daily_report.txt"
KEYWORDS_FILE="$WORKSPACE/keywords.txt"
LATEST_POSTER_JSON="$WORKSPACE/latest_poster.json"
LATEST_PLANNER_JSON="$WORKSPACE/latest_planner.json"
POSTER_PAYLOAD_JSON="$WORKSPACE/render_engine/payloads/generated_factory_poster.json"
TEST_MODE="${FACTORY_TEST_MODE:-0}"

source "$WORKSPACE/venv/bin/activate"
if [[ -f "$WORKSPACE/.env" ]]; then
  set -a
  source "$WORKSPACE/.env"
  set +a
fi

LOGO="
  █████╗ ██╗   ██╗████████╗██████╗
 ██╔══██╗██║   ██║╚══██╔══╝██╔══██╗
 ███████║██║   ██║   ██║   ██║  ██║
 ██╔══██║██║   ██║   ██║   ██║  ██║
 ██║  ██║╚██████╔╝   ██║   ██████╔╝
 ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚═════╝
        F A C T O R Y
"

run_python_json() {
  local output
  output=$(python3 "$@")
  echo "$output"
}

extract_json_field() {
  local json_payload="$1"
  local field_name="$2"
  python3 - "$json_payload" "$field_name" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
value = payload.get(sys.argv[2], '')
if isinstance(value, (list, dict)):
    print(json.dumps(value, ensure_ascii=False))
else:
    print(value)
PY
}

create_mockups_for_png() {
  local png_path="$1"
  local templates=("room_template1.jpg" "room_template2.jpg" "street_template.jpg")
  local template
  for template in "${templates[@]}"; do
    python3 "$WORKSPACE/mockup_generator.py" --png "$png_path" --template "$template"
  done
}

echo "$LOGO"
echo "========================================"
echo "🚀 [$(date)] Запуск Autofinisher Factory"
echo "========================================"

printf '<pre>%s</pre>\n' "$LOGO" > "$REPORT_FILE"
printf '<b>Factory Report: %s</b>\n\n' "$(date +'%Y-%m-%d')" >> "$REPORT_FILE"

python3 "$WORKSPACE/generate_logo.py"

printf '📝 <i>Line 1: Digital Planners</i>\n' >> "$REPORT_FILE"
python3 "$WORKSPACE/niche_scraper.py" --seed "digital planner" --limit 3

while IFS= read -r keyword; do
  [[ -z "$keyword" ]] && continue
  echo "⚙️ Planner niche: $keyword"
  planner_json=$(run_python_json "$WORKSPACE/api_factory_v2.py" --keyword "$keyword" --price 4.99)
  echo "$planner_json" > "$LATEST_PLANNER_JSON"
  planner_pdf=$(extract_json_field "$planner_json" "pdf_path")
  seo_json=$(run_python_json "$WORKSPACE/seo_generator.py" --keyword "$keyword")
  seo_path=$(extract_json_field "$seo_json" "seo_path")
  printf '✅ %s<br/>PDF: %s<br/>SEO: %s\n' "$keyword" "$planner_pdf" "$seo_path" >> "$REPORT_FILE"
done < "$KEYWORDS_FILE"

printf '\n🎨 <i>Line 2: Premium Raster Posters</i>\n' >> "$REPORT_FILE"
POSTER_KEYWORD="SYSTEM"
POSTER_TEMPLATE="${POSTER_TEMPLATE_ID:-swiss_brutalism}"
echo "⚙️ Poster phrase theme: $POSTER_KEYWORD"
payload_json=$(run_python_json "$WORKSPACE/render_engine/scripts/build_factory_payload.py" --keyword "$POSTER_KEYWORD" --template "$POSTER_TEMPLATE" --out "$POSTER_PAYLOAD_JSON")
poster_payload_path=$(extract_json_field "$payload_json" "payload_path")
poster_json=$(run_python_json "$WORKSPACE/render_engine/render.py" --payload "$poster_payload_path")
echo "$poster_json" > "$LATEST_POSTER_JSON"
poster_png=$(extract_json_field "$poster_json" "output_path")
poster_report=$(extract_json_field "$poster_json" "report_path")
poster_seo_json=$(run_python_json "$WORKSPACE/seo_generator.py" --keyword "$POSTER_KEYWORD poster")
poster_seo_path=$(extract_json_field "$poster_seo_json" "seo_path")
create_mockups_for_png "$poster_png"
printf '🖼 Poster PNG: %s<br/>Render Report: %s<br/>SEO: %s\n' "$poster_png" "$poster_report" "$poster_seo_path" >> "$REPORT_FILE"

printf '\n📁 All product generations completed.\n' >> "$REPORT_FILE"

if [[ "$TEST_MODE" == "1" ]]; then
  echo "🧪 FACTORY_TEST_MODE=1 -> Telegram notifier skipped"
else
  python3 "$WORKSPACE/telegram_notifier.py" --file "$REPORT_FILE"
fi

echo "✅ [$(date)] Цикл завершен."
