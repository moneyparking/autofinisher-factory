#!/bin/bash
WORKSPACE="/home/agent/autofinisher-factory"
REPORT_FILE="$WORKSPACE/daily_report.txt"
source $WORKSPACE/venv/bin/activate
set -a; source $WORKSPACE/.env; set +a

# Генерируем ASCII-логотип
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

# Формируем отчет для Telegram с тегом <pre> для сохранения форматирования
echo "<pre>$LOGO</pre>" > $REPORT_FILE
echo "<b>Утренний Отчет</b>" >> $REPORT_FILE
echo "<i>Новые ниши и товары:</i>" >> $REPORT_FILE
echo "" >> $REPORT_FILE

python3 $WORKSPACE/niche_scraper.py --seed "digital planner" --limit 5

while IFS= read -r keyword; do
    if [[ -n "$keyword" ]]; then
        echo "⚙️ Обработка: $keyword"
        python3 $WORKSPACE/api_factory_v2.py --keyword "$keyword" --price 4.99 > $WORKSPACE/latest_payload.json
        echo "✅ $keyword" >> $REPORT_FILE
        sleep 5
    fi
done < $WORKSPACE/keywords.txt

echo "" >> $REPORT_FILE
echo "📁 Черновики ожидают публикации!" >> $REPORT_FILE

python3 $WORKSPACE/telegram_notifier.py --file $REPORT_FILE
echo "✅ [$(date)] Цикл завершен."
