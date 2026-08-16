import requests
import json
import math
from datetime import datetime, timezone, timedelta

# Московское время
MSK_TZ = timezone(timedelta(hours=3))

# Координаты центра (Москва) и радиус 200 км
CENTER_LAT = 55.7558
CENTER_LNG = 37.6173
RADIUS_KM = 200

print(f"Запрашиваю ВСЕ заправки в радиусе {RADIUS_KM} км из OpenStreetMap...")

# Запрос к Overpass API (возвращает все объекты amenity=fuel)
overpass_url = "https://overpass-api.de/api/interpreter"
overpass_query = f"""
[out:json][timeout:180];
(
  node["amenity"="fuel"](around:{RADIUS_KM * 1000},{CENTER_LAT},{CENTER_LNG});
  way["amenity"="fuel"](around:{RADIUS_KM * 1000},{CENTER_LAT},{CENTER_LNG});
);
out center body;
"""

try:
    response = requests.get(overpass_url, data=overpass_query, timeout=200)
    response.raise_for_status()
    data = response.json()
except Exception as e:
    print(f"Ошибка при запросе к Overpass API: {e}")
    exit(1)

stations = []

for element in data.get('elements', []):
    # Получаем координаты
    if 'lat' in element:
        lat = element['lat']
        lng = element['lon']
    elif 'center' in element:
        lat = element['center']['lat']
        lng = element['center']['lon']
    else:
        continue
    
    # Теги (информация о заправке)
    tags = element.get('tags', {})
    
    # Название и бренд
    name = tags.get('name', 'АЗС')
    brand = tags.get('brand', tags.get('operator', name))
    
    # Адрес
    addr_street = tags.get('addr:street', '')
    addr_housenumber = tags.get('addr:housenumber', '')
    address = f"{addr_street}, {addr_housenumber}".strip(', ')
    if not address:
        address = "Адрес не указан"

    # Топливо (пытаемся понять из тегов, но часто их нет, тогда ставим стандартный набор)
    fuels = []
    fuel_map = {
        'fuel:octane_92': 'АИ-92',
        'fuel:octane_95': 'АИ-95',
        'fuel:octane_98': 'АИ-98',
        'fuel:diesel': 'ДТ',
        'fuel:lpg': 'Газ'
    }
    
    has_fuel_info = False
    for key, fuel_name in fuel_map.items():
        if tags.get(key) == 'yes':
            fuels.append({'type': fuel_name, 'price': 0, 'available': True})
            has_fuel_info = True
    
    # Если нет конкретной инфо, добавляем базовый набор (чтобы карточка не была пустой)
    if not has_fuel_info:
        fuels = [
            {'type': 'АИ-92', 'price': 0, 'available': None}, # None = неизвестно
            {'type': 'АИ-95', 'price': 0, 'available': None},
            {'type': 'ДТ', 'price': 0, 'available': None}
        ]

    station = {
        'id': f"osm-{element['id']}",
        'name': name,
        'brand': brand,
        'lat': lat,
        'lng': lng,
        'address': address,
        'fuels': fuels,
        'load': 'unknown', # По умолчанию нет данных о очереди
        'updated_at': datetime.now(MSK_TZ).isoformat()
    }
    
    stations.append(station)

print(f"Найдено заправок: {len(stations)}")

if len(stations) == 0:
    print("Ошибка: Не найдено ни одной заправки.")
    exit(1)

# Сохраняем
with open('data/stations.json', 'w', encoding='utf-8') as f:
    json.dump(stations, f, ensure_ascii=False, indent=2)

print("Данные сохранены в data/stations.json")
