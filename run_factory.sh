#!/bin/bash
echo "========================================"
echo "🚀 [$(date)] Запуск Autofinisher Factory"
echo "========================================"

WORKSPACE="/home/agent/autofinisher-factory"
source $WORKSPACE/venv/bin/activate
set -a; source $WORKSPACE/.env; set +a

# 1. Собираем свежие тренды (Берем только 5 самых горячих ниш на сегодня)
python3 $WORKSPACE/niche_scraper.py --seed "digital planner" --limit 5

# 2. Читаем собранные ниши и генерируем товары
while IFS= read -r keyword; do
    if [[ -n "$keyword" ]]; then
        echo "⚙️ Обработка ниши: $keyword"
        python3 $WORKSPACE/api_factory_v2.py --keyword "$keyword" --price 3.99 > $WORKSPACE/latest_payload.json
        # Здесь в будущем раскомментируем вызов Etsy/eBay Publisher
        # python3 $WORKSPACE/etsy_publisher.py --payload_file $WORKSPACE/latest_payload.json
        sleep 5
    fi
done < $WORKSPACE/keywords.txt

echo "✅ [$(date)] Цикл успешно завершен."
