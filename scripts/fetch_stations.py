import requests
import json
from datetime import datetime, timezone, timedelta
import time

# Московское время (UTC+3)
MSK_TZ = timezone(timedelta(hours=3))

# Координаты центра (Москва)
CENTER_LAT = 55.7558
CENTER_LNG = 37.6173

# Радиус поиска (200 км)
RADIUS_KM = 200

# Используем тот же API, что и сайт gdebenz.ru
API_URL = "https://api.gdebenz.ru/api/nearby"

print(f"Запрашиваю данные из {API_URL} (радиус {RADIUS_KM} км)...")

try:
    params = {
        'lat': CENTER_LAT,
        'lon': CENTER_LNG,
        'radius_km': RADIUS_KM,
        '_': int(time.time() * 1000) # Защита от кэша
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://gdebenz.ru/'
    }
    
    response = requests.get(API_URL, params=params, headers=headers, timeout=60)
    response.raise_for_status()
    
    data = response.json()
    
    # Данные могут быть в ключе 'stations' или сразу списком
    raw_stations = data.get('stations', data) if isinstance(data, dict) else data

except requests.exceptions.RequestException as e:
    print(f"Ошибка при запросе к API: {e}")
    exit(1)
except json.JSONDecodeError as e:
    print(f"Ошибка парсинга JSON: {e}")
    exit(1)

stations = []

for item in raw_stations:
    # Пропускаем, если нет координат
    if 'lat' not in item or 'lon' not in item:
        continue
    
    lat = float(item['lat'])
    lng = float(item['lon'])
    
    # --- ЛОГИКА СТАТУСА (КАК НА САЙТЕ) ---
    status = item.get('status', 'unknown')
    detail = item.get('detail', '')
    fuels_now_str = item.get('fuels_now', '')
    
    # Определяем load (цвет метки)
    if status == 'no':
        load = 'high' # Красный - нет топлива
    elif status == 'queue' or 'очередь' in detail.lower():
        load = 'medium' # Жёлтый - очередь
    elif status == 'yes':
        load = 'low' # Зелёный - есть
    else:
        load = 'unknown' # Серый - нет данных
    
    # --- ЛОГИКА ТОПЛИВА ---
    # Парсим строку "92,95,ДТ" в список
    available_fuels = []
    if fuels_now_str:
        available_fuels = [f.strip() for f in fuels_now_str.split(',')]
    
    # Формируем список всех видов топлива для отображения
    # Если статус 'no', то всё недоступно.
    # Если статус 'yes', то доступно только то, что в fuels_now (или всё, если список пуст, но статус yes - значит есть хоть что-то).
    
    all_fuels_types = ['92', '95', '98', '100', 'ДТ']
    fuels_list = []
    
    for fuel_code in all_fuels_types:
        # Нормализуем название для отображения
        display_name = f"АИ-{fuel_code}" if fuel_code.isdigit() else fuel_code
        
        is_available = False
        
        if load == 'high':
            is_available = False
        elif load == 'unknown':
            is_available = None # Неизвестно
        else:
            # Если есть конкретный список fuels_now
            if available_fuels:
                # Проверяем вхождение (учитывая, что может быть "92" или "АИ-92")
                is_available = any(fuel_code in f for f in available_fuels)
            else:
                # Если списка нет, но статус yes - считаем, что основное топливо есть
                # Но лучше показать как неизвестно, если нет точных данных
                is_available = True # Или None, если хочешь строже
            
        fuels_list.append({
            'type': display_name,
            'price': 0, # Цены в этом API нет, только наличие
            'available': is_available
        })

    # Название и бренд
    brand = item.get('brand', 'АЗС')
    name = item.get('name', brand)
    address = item.get('addr', '')
    
    # Время
    last_at_str = item.get('last_at', '')
    if last_at_str:
        try:
            # Парсим время (оно приходит без таймзоны, считаем как МСК)
            dt = datetime.strptime(last_at_str, "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=MSK_TZ)
            updated_at = dt.isoformat()
        except:
            updated_at = datetime.now(MSK_TZ).isoformat()
    else:
        updated_at = datetime.now(MSK_TZ).isoformat()

    station = {
        'id': item.get('osm_id', str(lat)+str(lng)),
        'name': name,
        'brand': brand,
        'lat': lat,
        'lng': lng,
        'address': address,
        'fuels': fuels_list,
        'load': load,
        'updated_at': updated_at
    }
    
    stations.append(station)

print(f"Найдено АЗС с данными: {len(stations)}")

# Статистика
green = sum(1 for s in stations if s['load'] == 'low')
yellow = sum(1 for s in stations if s['load'] == 'medium')
red = sum(1 for s in stations if s['load'] == 'high')
print(f"Зелёных (есть): {green}, Жёлтых (очередь): {yellow}, Красных (нет): {red}")

if len(stations) == 0:
    print("Ошибка: Не найдено ни одной АЗС. Возможно, API изменился.")
    exit(1)

# Сохраняем
with open('data/stations.json', 'w', encoding='utf-8') as f:
    json.dump(stations, f, ensure_ascii=False, indent=2)

print("Данные сохранены в data/stations.json")
