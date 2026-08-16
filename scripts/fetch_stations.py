import requests
import json
from datetime import datetime, timezone, timedelta
import time

# Московское время (UTC+3)
MSK_TZ = timezone(timedelta(hours=3))

# Координаты прямоугольника (Москва и область до ~100 км)
LAT1 = 54.5
LON1 = 36.0
LAT2 = 57.0
LON2 = 39.5

API_URL = "https://gdebenz.ru/api/stations"

print("Запрашиваю данные из gdebenz.ru...")

try:
    params = {
        'lat1': LAT1,
        'lon1': LON1,
        'lat2': LAT2,
        'lon2': LON2,
        '_': int(time.time() * 1000)
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://gdebenz.ru/moskva'
    }
    
    response = requests.get(API_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    
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

for item in data:
    if 'lat' not in item or 'lon' not in item:
        continue
    
    lat = float(item['lat'])
    lng = float(item['lon'])
    
    # Определяем статус и загруженность
    status = item.get('status', '')
    conflict = item.get('conflict', '')
    detail = item.get('detail', '')
    
    # Логика определения статуса
    if status == 'no' or 'не работает' in detail.lower():
        load = 'high'  # Нет топлива / не работает
    elif status == 'yes' and conflict == 'queue':
        load = 'medium'  # Есть топливо, но очередь
    elif status == 'yes':
        load = 'low'  # Есть топливо, нет очереди
    else:
        load = 'unknown'
    
    # Получаем бренд и название
    brand = item.get('brand', 'Неизвестно')
    name = item.get('name', brand)
    address = item.get('addr', 'Адрес не указан')
    
    # Получаем доступное топливо и цены
    fuels_now = item.get('fuels_now', '')
    prices_now = item.get('prices_now', {})
    fuels = []
    
    # Если статус "нет топлива", помечаем все как недоступные
    if load == 'high':
        fuels = [
            {'type': 'АИ-92', 'price': 0, 'available': False},
            {'type': 'АИ-95', 'price': 0, 'available': False},
            {'type': 'ДТ', 'price': 0, 'available': False}
        ]
    elif fuels_now:
        fuel_list = [f.strip() for f in fuels_now.split(',')]
        for fuel in fuel_list:
            fuel_type_map = {
                '92': 'АИ-92',
                '95': 'АИ-95',
                '98': 'АИ-98',
                '100': 'АИ-100',
                'ДТ': 'ДТ',
                'DT': 'ДТ'
            }
            fuel_name = fuel_type_map.get(fuel, fuel)
            
            # Получаем цену
            price = 0
            if fuel in prices_now:
                price_data = prices_now[fuel]
                if isinstance(price_data, dict):
                    price = price_data.get('p', 0)
                elif isinstance(price_data, (int, float)):
                    price = price_data
            
            fuels.append({
                'type': fuel_name,
                'price': round(price, 2) if price else 0,
                'available': True
            })
    
    # Если нет информации о топливе и статус неизвестен
    if not fuels:
        fuels = [
            {'type': 'АИ-92', 'price': 0, 'available': True},
            {'type': 'АИ-95', 'price': 0, 'available': True},
            {'type': 'ДТ', 'price': 0, 'available': True}
        ]
    
    # Время последнего обновления в московском часовом поясе
    last_at_str = item.get('last_at', '')
    if last_at_str:
        try:
            # Парсим время и конвертируем в МСК
            dt = datetime.fromisoformat(last_at_str.replace('Z', '+00:00'))
            dt_msk = dt.astimezone(MSK_TZ)
            last_at = dt_msk.isoformat()
        except:
            last_at = datetime.now(MSK_TZ).isoformat()
    else:
        last_at = datetime.now(MSK_TZ).isoformat()
    
    station = {
        'id': f"azs-{item.get('osm_id', id(item))}",
        'name': name,
        'brand': brand,
        'lat': lat,
        'lng': lng,
        'address': address,
        'fuels': fuels,
        'load': load,
        'updated_at': last_at
    }
    
    stations.append(station)

print(f"Найдено АЗС: {len(stations)}")

# Подсчёт статистики
with_fuel = sum(1 for s in stations if s['load'] == 'low')
with_queue = sum(1 for s in stations if s['load'] == 'medium')
no_fuel = sum(1 for s in stations if s['load'] == 'high')
with_prices = sum(1 for s in stations if any(f['price'] > 0 for f in s['fuels']))

print(f"С топливом: {with_fuel}")
print(f"С очередью: {with_queue}")
print(f"Без топлива: {no_fuel}")
print(f"С ценами: {with_prices}")

if len(stations) == 0:
    print("Предупреждение: Не найдено ни одной АЗС.")
    exit(1)

# Сохраняем в файл
with open('data/stations.json', 'w', encoding='utf-8') as f:
    json.dump(stations, f, ensure_ascii=False, indent=2)

print("Данные сохранены в data/stations.json")
