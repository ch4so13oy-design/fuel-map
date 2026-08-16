import requests
import json
import math
from datetime import datetime

# Координаты центра (Москва)
CENTER_LAT = 55.7558
CENTER_LNG = 37.6173
RADIUS_KM = 200

# Функция для расчёта расстояния между двумя точками (формула гаверсинусов)
def haversine(lat1, lng1, lat2, lng2):
    R = 6371  # Радиус Земли в км
    dLat = math.radians(lat2 - lat1)
    dLng = math.radians(lng2 - lng1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# Запрос к Overpass API для получения всех АЗС в радиусе 200 км от Москвы
overpass_url = "https://overpass-api.de/api/interpreter"
overpass_query = f"""
[out:json][timeout:60];
(
  node["amenity"="fuel"](around:{RADIUS_KM * 1000},{CENTER_LAT},{CENTER_LNG});
  way["amenity"="fuel"](around:{RADIUS_KM * 1000},{CENTER_LAT},{CENTER_LNG});
  relation["amenity"="fuel"](around:{RADIUS_KM * 1000},{CENTER_LAT},{CENTER_LNG});
);
out center body;
"""

print("Запрашиваю данные из OpenStreetMap...")
response = requests.get(overpass_url, data=overpass_query)
data = response.json()

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
    
    # Проверяем расстояние (дополнительная проверка)
    distance = haversine(CENTER_LAT, CENTER_LNG, lat, lng)
    if distance > RADIUS_KM:
        continue
    
    # Получаем теги
    tags = element.get('tags', {})
    
    # Определяем название и бренд
    name = tags.get('name', 'АЗС')
    brand = tags.get('brand', tags.get('operator', 'Неизвестно'))
    address = tags.get('addr:street', '') + ', ' + tags.get('addr:housenumber', '')
    address = address.strip(', ')
    
    # Определяем виды топлива
    fuels = []
    fuel_types = {
        'fuel:octane_92': 'АИ-92',
        'fuel:octane_95': 'АИ-95',
        'fuel:octane_98': 'АИ-98',
        'fuel:diesel': 'ДТ',
        'fuel:lpg': 'Газ'
    }
    
    for key, fuel_name in fuel_types.items():
        if tags.get(key) == 'yes':
            fuels.append({
                'type': fuel_name,
                'price': 0,
                'available': True
            })
    
    # Если нет информации о топливе, добавляем базовый набор
    if not fuels:
        fuels = [
            {'type': 'АИ-92', 'price': 0, 'available': True},
            {'type': 'АИ-95', 'price': 0, 'available': True},
            {'type': 'ДТ', 'price': 0, 'available': True}
        ]
    
    station = {
        'id': f"azs-{element['id']}",
        'name': name,
        'brand': brand,
        'lat': lat,
        'lng': lng,
        'address': address if address else 'Адрес не указан',
        'fuels': fuels,
        'load': 'unknown',
        'updated_at': datetime.utcnow().isoformat() + 'Z'
    }
    
    stations.append(station)

print(f"Найдено АЗС: {len(stations)}")

# Сохраняем в файл
with open('data/stations.json', 'w', encoding='utf-8') as f:
    json.dump(stations, f, ensure_ascii=False, indent=2)

print("Данные сохранены в data/stations.json")
