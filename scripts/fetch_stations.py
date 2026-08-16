import requests
import json
from datetime import datetime, timezone, timedelta
import time

# Московское время (UTC+3)
MSK_TZ = timezone(timedelta(hours=3))

# Координаты центра (Москва)
CENTER_LAT = 55.7558
CENTER_LNG = 37.6173
RADIUS_KM = 200

# Используем основной домен, как в браузере
API_URL = "https://gdebenz.ru/api/nearby"

print(f"Запрашиваю данные из {API_URL} (радиус {RADIUS_KM} км)...")

try:
    params = {
        'lat': CENTER_LAT,
        'lon': CENTER_LNG,
        'radius_km': RADIUS_KM,
        '_': int(time.time() * 1000) # Защита от кэша
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://gdebenz.ru/'
    }
    
    response = requests.get(API_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    
    # В ответе приходит сразу список [...] или объект. Проверим оба варианта.
    data = response.json()
    
    # Если данные внутри ключа 'stations' (на всякий случай)
    if isinstance(data, dict) and 'stations' in data:
        raw_stations = data['stations']
    elif isinstance(data, list):
        raw_stations = data
    else:
        print("Неизвестный формат ответа API")
        print(data)
        exit(1)

except requests.exceptions.RequestException as e:
    print(f"Ошибка при запросе к API: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Код ответа: {e.response.status_code}")
        print(f"Текст ответа: {e.response.text[:500]}")
    exit(1)
except json.JSONDecodeError as e:
    print(f"Ошибка парсинга JSON: {e}")
    exit(1)

stations = []

for item in raw_stations:
    # Пропускаем, если нет координат
    if 'lat' not in item or 'lon' not in item:
        continue
    
    try:
        lat = float(item['lat'])
        lng = float(item['lon'])
    except (ValueError, TypeError):
        continue

    # --- ЛОГИКА СТАТУСА ---
    # В твоем файле были поля: status ("yes", "no"), fuels_now ("92,95"), conflict ("queue")
    status = item.get('status', '') 
    fuels_now_str = item.get('fuels_now', '')
    conflict = item.get('conflict', '')
    
    # Определяем load (цвет кружка)
    if status == 'no':
        load = 'high' # Красный
    elif conflict == 'queue' or 'очередь' in str(item.get('detail', '')).lower():
        load = 'medium' # Желтый
    elif status == 'yes':
        load = 'low' # Зеленый
    else:
        # Если статуса нет, но есть топливо в списке, считаем зеленым
        if fuels_now_str:
            load = 'low'
        else:
            load = 'unknown' # Серый

    # --- ЛОГИКА ТОПЛИВА ---
    fuels_list = []
    
    # Парсим строку наличия "92,95,ДТ"
    available_types = []
    if fuels_now_str:
        available_types = [x.strip() for x in fuels_now_str.split(',')]

    # Список всех возможных типов для отображения
    all_types = {'92': 'АИ-92', '95': 'АИ-95', '98': 'АИ-98', '100': 'АИ-100', 'ДТ': 'ДТ', 'DT': 'ДТ'}
    
    # Цены (если есть в ответе, в твоем примере их не было в корне, но проверим prices_now)
    prices = item.get('prices_now', {})

    for code, name in all_types.items():
        # Проверяем наличие
        is_available = None
        
        if status == 'no':
            is_available = False
        elif status == 'yes' or fuels_now_str:
            # Если есть список fuels_now, проверяем по нему
            if available_types:
                is_available = code in available_types
            else:
                # Если списка нет, но статус yes - предполагаем, что всё есть (или неизвестно)
                # Но лучше поставить None, если нет точных данных
                is_available = True 
        
        # Цена
        price = 0
        if code in prices:
            p_data = prices[code]
            if isinstance(p_data, dict):
                price = p_data.get('p', 0)
            elif isinstance(p_data, (int, float)):
                price = p_data
        
        # Добавляем в список, только если есть информация или это важный тип
        # Чтобы не засорять, добавим всё, но с правильным статусом
        fuels_list.append({
            'type': name,
            'price': round(float(price), 2) if price else 0,
            'available': is_available
        })

    # Название и бренд
    brand = item.get('brand', 'АЗС')
    name = item.get('name', brand)
    address = item.get('addr', item.get('address', ''))
    
    # Время
    updated_at = datetime.now(MSK_TZ).isoformat()
    if 'updated_at' in item:
        updated_at = item['updated_at']
    elif 'last_at' in item:
         updated_at = item['last_at']

    stations.append({
        'id': str(item.get('id', item.get('osm_id', f"{lat}{lng}"))),
        'name': name,
        'brand': brand,
        'lat': lat,
        'lng': lng,
        'address': address,
        'fuels': fuels_list,
        'load': load,
        'updated_at': updated_at
    })

print(f"Найдено АЗС: {len(stations)}")

# Статистика
green = sum(1 for s in stations if s['load'] == 'low')
yellow = sum(1 for s in stations if s['load'] == 'medium')
red = sum(1 for s in stations if s['load'] == 'high')
print(f"Зеленых: {green}, Желтых: {yellow}, Красных: {red}")

if not stations:
    print("Ошибка: Список пуст")
    exit(1)

with open('data/stations.json', 'w', encoding='utf-8') as f:
    json.dump(stations, f, ensure_ascii=False, indent=2)

print("Данные сохранены.")
