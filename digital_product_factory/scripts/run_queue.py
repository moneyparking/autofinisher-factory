from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

QUEUE_PATH = Path('/home/agent/autofinisher-factory/digital_product_factory/configs/products_queue.json')
SCRIPT_PATH = Path('/home/agent/autofinisher-factory/digital_product_factory/scripts/run_product.py')


def run_product(product_id: int) -> None:
    subprocess.run(['python3', str(SCRIPT_PATH), str(product_id)], check=True)


def main() -> None:
    payload = json.loads(QUEUE_PATH.read_text(encoding='utf-8'))
    product_ids = [int(item['product_id']) for item in payload.get('items', []) if item.get('status') == 'queued']
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run_product, product_ids))


if __name__ == '__main__':
    main()
