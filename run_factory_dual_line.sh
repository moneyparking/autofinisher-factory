#!/bin/bash
WORKSPACE="/home/agent/autofinisher-factory"
REPORT_FILE="$WORKSPACE/daily_report.txt"
source $WORKSPACE/venv/bin/activate
set -a; source $WORKSPACE/.env; set +a

LOGO="
  █████╗ ██╗   ██╗████████╗██████╗ 
 ██╔══██╗██║   ██║╚══██╔══╝██╔══██╗
 ███████║██║   ██║   ██║   ██║  ██║
 ██╔══██║██║   ██║   ██║   ██║  ██║
 ██║  ██║╚██████╔╝   ██║   ██████╔╝
 ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚═════╝ 
        F A C T O R Y
"

echo "$LOGO"
echo "========================================"
echo "🚀 [$(date)] Запуск Autofinisher Factory"
echo "========================================"

echo "<pre>$LOGO</pre>" > $REPORT_FILE
echo "<b>Утренний Отчет: $(date +'%Y-%m-%d')</b>" >> $REPORT_FILE
echo "" >> $REPORT_FILE

# ЛИНИЯ 1: Digital Planners
echo "📝 <i>Линия 1: Digital Planners</i>" >> $REPORT_FILE
python3 $WORKSPACE/niche_scraper.py --seed "digital planner" --limit 3

while IFS= read -r keyword; do
    if [[ -n "$keyword" ]]; then
        echo "⚙️ Планер: $keyword"
        python3 $WORKSPACE/api_factory_v2.py --keyword "$keyword" --price 4.99 > $WORKSPACE/latest_planner.json
        echo "✅ $keyword" >> $REPORT_FILE
        sleep 3
    fi
done < $WORKSPACE/keywords.txt

echo "" >> $REPORT_FILE

# ЛИНИЯ 2: Dev Merch (ASCII Posters)
echo "🎨 <i>Линия 2: ASCII IT Posters</i>" >> $REPORT_FILE
DEV_KEYWORDS=("CYBERSECURITY" "DEVOPS" "PROMPT ENGINEER")

for dev_word in "${DEV_KEYWORDS[@]}"; do
    echo "⚙️ Постер: $dev_word"
    python3 $WORKSPACE/ascii_poster_factory.py --keyword "$dev_word" --price 9.99 > $WORKSPACE/latest_poster.json
    echo "🖼 $dev_word" >> $REPORT_FILE
    sleep 2
done

echo "" >> $REPORT_FILE
echo "📁 Все генерации завершены и ждут публикации!" >> $REPORT_FILE

# Отправка отчета
python3 $WORKSPACE/telegram_notifier.py --file $REPORT_FILE
echo "✅ [$(date)] Цикл завершен."
