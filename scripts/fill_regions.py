import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Region

# Актуальный список регионов Яндекса
REGIONS = [
    (225, "Россия"),
    (11235, "Алтайский край"),
    (11375, "Амурская область"),
    (10842, "Архангельская область"),
    (10946, "Астраханская область"),
    (10645, "Белгородская область"),
    (10650, "Брянская область"),
    (10658, "Владимирская область"),
    (10950, "Волгоградская область"),
    (10853, "Вологодская область"),
    (10672, "Воронежская область"),
    (10687, "Ивановская область"),
    (11266, "Иркутская область"),
    (11013, "Кабардино-Балкарская Республика"),
    (10857, "Калининградская область"),
    (11020, "Карачаево-Черкесская Республика"),
    (11282, "Кемеровская область (Кузбасс)"),
    (10699, "Костромская область"),
    (10995, "Краснодарский край"),
    (11309, "Красноярский край"),
    (11158, "Курганская область"),
    (10705, "Курская область"),
    (10712, "Липецкая область"),
    (1, "Москва и Московская область"),
    (10897, "Мурманская область"),
    (11079, "Нижегородская область"),
    (10904, "Новгородская область"),
    (11316, "Новосибирская область"),
    (11318, "Омская область"),
    (11084, "Оренбургская область"),
    (10772, "Орловская область"),
    (11095, "Пензенская область"),
    (11108, "Пермский край"),
    (11409, "Приморский край"),
    (10926, "Псковская область"),
    (11111, "Республика Башкортостан"),
    (11010, "Республика Дагестан"),
    (11012, "Республика Ингушетия"),
    (11077, "Республика Марий Эл"),
    (11117, "Республика Мордовия"),
    (11021, "Республика Северная Осетия — Алания"),
    (11119, "Республика Татарстан"),
    (11029, "Ростовская область"),
    (10776, "Рязанская область"),
    (11131, "Самарская область"),
    (10174, "Санкт-Петербург и Ленинградская область"),
    (11162, "Свердловская область"),
    (10795, "Смоленская область"),
    (11069, "Ставропольский край"),
    (10802, "Тамбовская область"),
    (10819, "Тверская область"),
    (11353, "Томская область"),
    (10832, "Тульская область"),
    (11153, "Ульяновская область"),
    (11457, "Хабаровский край"),
    (11193, "Ханты-Мансийский автономный округ - Югра"),
    (11225, "Челябинская область"),
    (11024, "Чеченская Республика"),
    (11156, "Чувашская Республика"),
    (10841, "Ярославская область")
]

def fill_regions():
    app = create_app()
    with app.app_context():
        print("Удаляем старые регионы...")
        Region.query.delete()
        db.session.commit()
        
        print("Добавляем новые регионы в базу данных...")
        for yandex_id, name in REGIONS:
            region = Region(yandex_id=yandex_id, name=name)
            db.session.add(region)
            print(f"Добавлен регион: {name} (ID: {yandex_id})")
        
        db.session.commit()
        print("Регионы успешно обновлены!")

if __name__ == '__main__':
    fill_regions()