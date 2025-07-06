from datetime import datetime, timedelta

def get_game_time():
    """Фиксированное время UTC+1"""
    return datetime.utcnow() + timedelta(hours=1)

def parse_time(time_str):
    """Конвертация строки времени"""
    return datetime.strptime(time_str, "%H:%M").time()