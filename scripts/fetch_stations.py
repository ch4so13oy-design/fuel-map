import requests
import json
from datetime import datetime
import time

# Координаты прямоугольника (Москва и область до ~100 км)
# lat1, lon1 - юго-западный угол
# lat2, lon2 - северо-восточный угол
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
    # Пропускаем заправки без координат
    if 'lat' not in item or 'lon' not in item:
        continue
    
    lat = float(item['lat'])
    lng = float(item['lon'])
    
    # Определяем статус
    status = item.get('status', 'unknown')
    if status == 'yes':
        load = 'low'  # Есть топливо
    elif status == 'no':
        load = 'high'  # Нет топлива
    else:
        load = 'unknown'
    
    # Проверяем очередь
    conflict = item.get('conflict', '')
    if conflict == 'queue':
        load = 'medium'  # Очередь
    
    # Получаем бренд и название
    brand = item.get('brand', 'Неизвестно')
    name = item.get('name', brand)
    address = item.get('addr', 'Адрес не указан')
    
    # Получаем доступное топливо
    fuels_now = item.get('fuels_now', '')
    fuels = []
    
    if fuels_now:
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
            
            # Получаем цену если есть
            price = 0
            prices = item.get('prices_now', {})
            if fuel in prices:
                price = prices[fuel].get('p', 0)
            
            fuels.append({
                'type': fuel_name,
                'price': price,
                'available': True
            })
    
    # Если нет информации о топливе, добавляем базовый набор
    if not fuels:
        fuels = [
            {'type': 'АИ-92', 'price': 0, 'available': True},
            {'type': 'АИ-95', 'price': 0, 'available': True},
            {'type': 'ДТ', 'price': 0, 'available': True}
        ]
    
    # Время последнего обновления
    last_at = item.get('last_at', datetime.utcnow().isoformat())
    
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

if len(stations) == 0:
    print("Предупреждение: Не найдено ни одной АЗС.")
    exit(1)

# Сохраняем в файл
with open('data/stations.json', 'w', encoding='utf-8') as f:
    json.dump(stations, f, ensure_ascii=False, indent=2)

print("Данные сохранены в data/stations.json")
