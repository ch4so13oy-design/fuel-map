import requests
import json
import time
from datetime import datetime, timezone, timedelta

# Московское время
MSK_TZ = timezone(timedelta(hours=3))

# Используем API gdebenz.ru (он работает стабильно)
API_URL = "https://gdebenz.ru/api/stations"

# Координаты прямоугольника (Москва и область ~200км)
# lat1, lon1 - юго-запад
# lat2, lon2 - северо-восток
PARAMS = {
    'lat1': 54.5,
    'lon1': 36.0,
    'lat2': 57.0,
    'lon2': 39.5,
    '_': int(time.time() * 1000) # Защита от кэша
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json',
    'Referer': 'https://gdebenz.ru/moskva'
}

print(f"Запрашиваю данные из {API_URL}...")

try:
    response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=30)
    response.raise_for_status()
    
    # Пробуем распарсить JSON
    try:
        data = response.json()
    except json.JSONDecodeError:
        print("Ошибка: Сервер вернул не JSON.")
        print(response.text[:200])
        exit(1)

    # Данные могут быть в списке или в ключе 'stations'
    raw_stations = []
    if isinstance(data, list):
        raw_stations = data
    elif isinstance(data, dict) and 'stations' in data:
        raw_stations = data['stations']
    else:
        print("Неизвестный формат данных")
        exit(1)

except requests.exceptions.RequestException as e:
    print(f"Ошибка сети: {e}")
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

    # --- Логика статуса ---
    status = item.get('status', '')
    conflict = item.get('conflict', '')
    
    if status == 'no':
        load = 'high' # Красный
    elif conflict == 'queue' or 'очередь' in str(item.get('detail', '')).lower():
        load = 'medium' # Желтый
    elif status == 'yes':
        load = 'low' # Зеленый
    else:
        load = 'unknown' # Серый

    # --- Логика топлива ---
    fuels_now_str = item.get('fuels_now', '')
    prices_now = item.get('prices_now', {})
    
    fuels_list = []
    
    # Если есть список доступного топлива
    if fuels_now_str:
        available_types = [f.strip() for f in fuels_now_str.split(',')]
        
        # Проходим по всем возможным типам
        all_types = {'92': 'АИ-92', '95': 'АИ-95', '98': 'АИ-98', '100': 'АИ-100', 'ДТ': 'ДТ', 'DT': 'ДТ'}
        
        for code, name in all_types.items():
            is_available = code in available_types
            
            # Цена
            price = 0
            if code in prices_now:
                p_data = prices_now[code]
                if isinstance(p_data, dict):
                    price = p_data.get('p', 0)
                elif isinstance(p_data, (int, float)):
                    price = p_data
            
            # Добавляем только если топливо есть в списке ИЛИ если цена есть (иногда цены есть, а списка нет)
            if is_available or price > 0:
                 fuels_list.append({
                    'type': name,
                    'price': round(float(price), 2) if price else 0,
                    'available': is_available if is_available else (True if price > 0 else None)
                })
    
    # Если список пустой, но статус 'yes' или 'unknown', добавляем заглушки
    if not fuels_list:
        if load in ['low', 'unknown']:
             fuels_list = [
                {'type': 'АИ-92', 'price': 0, 'available': None},
                {'type': 'АИ-95', 'price': 0, 'available': None},
                {'type': 'ДТ', 'price': 0, 'available': None}
            ]
        elif load == 'high':
             fuels_list = [
                {'type': 'АИ-92', 'price': 0, 'available': False},
                {'type': 'АИ-95', 'price': 0, 'available': False},
                {'type': 'ДТ', 'price': 0, 'available': False}
            ]

    # Время
    last_at_str = item.get('last_at', '')
    if last_at_str:
        try:
            # Формат "2026-08-16 06:45:31"
            dt = datetime.strptime(last_at_str, "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=MSK_TZ)
            updated_at = dt.isoformat()
        except:
            updated_at = datetime.now(MSK_TZ).isoformat()
    else:
        updated_at = datetime.now(MSK_TZ).isoformat()

    stations.append({
        'id': str(item.get('osm_id', item.get('id', f"{lat}{lng}"))),
        'name': item.get('name', 'АЗС'),
        'brand': item.get('brand', ''),
        'lat': lat,
        'lng': lng,
        'address': item.get('addr', item.get('address', '')),
        'fuels': fuels_list,
        'load': load,
        'updated_at': updated_at
    })

print(f"Найдено заправок: {len(stations)}")

if not stations:
    print("Ошибка: Список пуст")
    exit(1)

# Сохраняем
with open('data/stations.json', 'w', encoding='utf-8') as f:
    json.dump(stations, f, ensure_ascii=False, indent=2)

print("Данные сохранены.")
