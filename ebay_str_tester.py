import re
import time
from bs4 import BeautifulSoup
from curl_cffi import requests

def get_ebay_count(keyword, sold_only=False):
    url = f"https://www.ebay.com/sch/i.html?_nkw={keyword.replace(' ', '+')}"
    if sold_only:
        url += "&LH_Sold=1&LH_Complete=1"
        
    try:
        # Магия здесь: impersonate="chrome" заставляет пакет выглядеть как реальный браузер
        response = requests.get(url, impersonate="chrome", timeout=15)
        
        if response.status_code != 200:
            print(f"Ошибка доступа: eBay вернул код {response.status_code}")
            return 0

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Парсим количество результатов
        heading = soup.select_one('.srp-controls__count-heading')
        if heading:
            match = re.search(r'([\d,]+)', heading.text)
            if match:
                return int(match.group(1).replace(',', ''))
        else:
            print("Заголовок с цифрами не найден. Возможно, капча.")
            
        return 0
        
    except Exception as e:
        print(f"Ошибка соединения: {e}")
        return 0

def run_financial_report(keyword):
    print(f"--- АНАЛИЗ РЫНКА (TLS Bypass STR) ---")
    print(f"Ниша (Keyword): '{keyword}'\n")
    
    print("Собираем данные по активным листингам (Supply)...")
    active_count = get_ebay_count(keyword, sold_only=False)
    
    time.sleep(2) # Небольшая пауза
    
    print("Собираем данные по проданным товарам (Demand)...")
    sold_count = get_ebay_count(keyword, sold_only=True)
    
    str_percentage = 0
    if active_count > 0:
        str_percentage = (sold_count / active_count) * 100
        
    print("\n--- ФИНАНСОВЫЙ ОТЧЕТ ---")
    print(f"Активные конкуренты (Supply): {active_count}")
    print(f"Успешные продажи (Demand):   {sold_count}")
    print(f"Sell-Through Rate (STR):     {str_percentage:.2f}%")
    
    if str_percentage >= 50:
        print("Вердикт: ИДЕАЛЬНАЯ НИША (Зеленый свет для конвейера)")
    elif str_percentage >= 20:
        print("Вердикт: НОРМАЛЬНО (Можно тестировать с хорошим SEO)")
    else:
        print("Вердикт: ПЕРЕГРЕТО / НЕТ СПРОСА (Сменить семантический атом)")

if __name__ == "__main__":
    target_niche = "digital planner"
    run_financial_report(target_niche)
