import discord
from discord.ext import commands, tasks
import json
import logging
import os
import random
from dotenv import load_dotenv
from time_utils import get_game_time, parse_time
from datetime import datetime, timedelta

# ======================
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# ======================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='bot.log',
    encoding='utf-8'
)

# ======================
# ЗАГРУЗКА КОНФИГУРАЦИИ
# ======================
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    logging.info("Конфиг config.json загружен")
except Exception as e:
    logging.critical(f"Ошибка загрузки config.json: {e}")
    exit()

# Загрузка токена из .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    logging.critical("Токен не найден в .env файле!")
    exit()

# ======================
# ИНИЦИАЛИЗАЦИЯ БОТА
# ======================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None  # Отключаем стандартную команду помощи
)

# ======================
# ФУНКЦИИ ДЛЯ РАБОТЫ С СОБЫТИЯМИ
# ======================
def load_events():
    """Загрузка расписания из events.json"""
    try:
        with open('events.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки events.json: {e}")
        return {}

@tasks.loop(seconds=30)
async def check_events():
    """Фоновая проверка событий"""
    try:
        game_time = get_game_time()
        current_time = game_time.strftime("%H:%M")
        current_day = game_time.strftime("%A").lower()
        events_data = load_events()

        for event in events_data.get(current_day, []) + events_data.get("daily", []):
            event_time = datetime.combine(game_time.date(), parse_time(event["start"]))
            remind_time = event_time - timedelta(minutes=config["REMIND_BEFORE_MINUTES"])
            
            if current_time == remind_time.strftime("%H:%M"):
                channel = bot.get_channel(config["CHANNEL_ID"])
                if channel:
                    ping_target = event.get('role_to_ping', '@everyone')
                    await channel.send(
                        f"🔔 {ping_target} Через {config['REMIND_BEFORE_MINUTES']} минут: {event['name']}"
                    )
                    logging.info(f"Отправлено уведомление: {event['name']}")

    except Exception as e:
        logging.error(f"Ошибка в check_events: {e}")

# ======================
# КОМАНДЫ БОТА
# ======================
@bot.command()
async def events(ctx, day: str = None):
    """Показать расписание на день"""
    try:
        events_data = load_events()
        if not events_data:
            await ctx.send("⛔ Расписание временно недоступно")
            return

        game_time = get_game_time()
        requested_day = day.lower() if day else game_time.strftime("%A").lower()
        events_list = events_data.get(requested_day, []) + events_data.get("daily", [])

        if not events_list:
            await ctx.send(f"📭 На {requested_day.capitalize()} ивентов нет")
            return

        # Сортируем и форматируем
        events_list.sort(key=lambda x: x["start"])
        message = f"📅 {requested_day.capitalize()}\n⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        
        for event in events_list:
            hour = int(event["start"][:2]) % 12 or 12
            message += f"• :clock{hour}: {event['start']}-{event['end']}: {event['name']}\n"

        await ctx.send(message)

    except Exception as e:
        logging.error(f"Ошибка команды events: {e}")
        await ctx.send("❌ Ошибка при загрузке расписания")

@bot.command()
async def debugtime(ctx):
    """Показывает текущее игровое время и ближайшее событие"""
    try:
        game_time = get_game_time()
        current_time_str = game_time.strftime("%H:%M")
        current_day = game_time.strftime("%A").lower()
        events_data = load_events()
        
        # Получаем все события на текущий день
        today_events = events_data.get(current_day, []) + events_data.get("daily", [])
        
        # Ищем ближайшее событие
        next_event = None
        min_diff = float('inf')
        
        for event in today_events:
            event_time = parse_time(event["start"])
            event_datetime = datetime.combine(game_time.date(), event_time)
            
            # Вычисляем разницу во времени (в минутах)
            time_diff = (event_datetime - game_time).total_seconds() / 60
            
            # Ищем ближайшее будущее событие
            if 0 < time_diff < min_diff:
                min_diff = time_diff
                next_event = event
        
        # Формируем сообщение
        message = (
            f"⏰ **Текущее игровое время (UTC+1):** {current_time_str}\n"
            f"📅 **Дата:** {game_time.strftime('%d.%m.%Y')}\n"
            "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        )
        
        if next_event:
            message += (
                f"▶ **Ближайшее событие:** {next_event['name']}\n"
                f"🕒 **Начнётся через:** {int(min_diff)} мин. (в {next_event['start']})"
            )
        else:
            message += "⏳ На сегодня событий больше нет"
            
        await ctx.send(message)
        
    except Exception as e:
        logging.error(f"Ошибка в debugtime: {e}")
        await ctx.send("❌ Ошибка при проверке времени")

# ======================
# СИСТЕМНЫЕ СОБЫТИЯ
# ======================
@bot.event
async def on_ready():
    """Действия при запуске бота"""
    print("\n" + "="*50)
    print(f"Бот {bot.user.name} успешно подключился!")
    print(f"Серверов: {len(bot.guilds)}")
    print(f"ID: {bot.user.id}")
    print("="*50 + "\n")

    # Устанавливаем кастомный статус
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="за Хаосом 👁️",
            details="Отслеживаю события"
        ),
        status=discord.Status.online
    )
    logging.info(f"Бот запущен с статусом 'Смотрит за Хаосом'")

    # Запускаем фоновые задачи
    check_events.start()

# ======================
# ЗАПУСК БОТА
# ======================
if __name__ == "__main__":
    print("="*50)
    print("Инициализация бота Alice...")
    print("Проверка конфигурации:")
    print(f"• Токен: {'найден' if TOKEN else '❌ ОШИБКА'}")
    print(f"• Канал: {config.get('CHANNEL_ID', '❌ не указан')}")
    print(f"• Часовой пояс: UTC+1")
    print("="*50)

    try:
        bot.run(TOKEN)
    except discord.LoginError:
        print("❌ Ошибка: Неверный токен! Проверьте .env файл")
    except Exception as e:
        print(f"❌ Критическая ошибка: {str(e)}")
    finally:
        print("="*50)