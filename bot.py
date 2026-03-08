# bot.py - основной файл бота

# ========== ПОДКЛЮЧЕНИЕ БИБЛИОТЕК ==========

import discord  # основная библиотека для Discord
from discord.ext import commands, tasks  # дополнительные функции
import os  # для работы с файлами и переменными окружения
import asyncio  # для асинхронных операций
from dotenv import load_dotenv  # для загрузки .env файла
import logging  # для записи логов
from datetime import datetime  # для работы с датой и временем

# ========== ЗАГРУЗКА ПЕРЕМЕННЫХ ==========

# Загружаем переменные из .env файла
load_dotenv()

# Получаем токен из переменных окружения
TOKEN = os.getenv('DISCORD_TOKEN')
VOICE_CHANNEL_ID = os.getenv('VOICE_CHANNEL_ID')

# Проверяем, что токен загрузился
if not TOKEN:
    raise ValueError("❌ Токен не найден! Проверьте файл .env")

if not VOICE_CHANNEL_ID:
    raise ValueError("❌ ID канала не найден! Проверьте файл .env")

# Преобразуем ID канала в число
try:
    VOICE_CHANNEL_ID = int(VOICE_CHANNEL_ID)
except ValueError:
    raise ValueError("❌ ID канала должен быть числом!")

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========

# Настраиваем запись логов в файл и вывод в консоль
logging.basicConfig(
    level=logging.INFO,  # уровень логирования (INFO, DEBUG, ERROR)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # формат сообщений
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),  # запись в файл
        logging.StreamHandler()  # вывод в консоль
    ]
)

logger = logging.getLogger(__name__)  # создаем логгер для текущего файла

# ========== НАСТРОЙКА ПРАВ БОТА ==========

# Настраиваем разрешения (Intents)
intents = discord.Intents.default()  # базовые разрешения
intents.message_content = True  # разрешаем читать сообщения (ОЧЕНЬ ВАЖНО!)
intents.voice_states = True  # разрешаем отслеживать голосовые каналы

# Создаем бота с префиксом "!" для команд
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ========== КЛАСС ДЛЯ УПРАВЛЕНИЯ ГОЛОСОМ ==========

class VoiceManager:
    """Класс для управления подключением к голосовым каналам"""
    
    def __init__(self):
        self.target_channel_id = VOICE_CHANNEL_ID  # ID целевого канала
        self.reconnect_attempts = 0  # счетчик попыток переподключения
        self.max_attempts = 5  # максимум попыток
        self.is_connected = False  # флаг подключения
        self.voice_client = None  # объект голосового клиента
        
    async def connect_to_channel(self, channel):
        """
        Подключение к голосовому каналу
        channel - объект голосового канала Discord
        """
        try:
            # Проверяем, есть ли уже подключение на этом сервере
            if channel.guild.voice_client:
                # Если есть - перемещаемся в новый канал
                await channel.guild.voice_client.move_to(channel)
                self.voice_client = channel.guild.voice_client
                logger.info(f"✅ Переместился в канал: {channel.name}")
            else:
                # Если нет - подключаемся
                self.voice_client = await channel.connect()
                logger.info(f"✅ Подключился к каналу: {channel.name}")
            
            self.is_connected = True
            self.reconnect_attempts = 0
            return True
            
        except Exception as e:
            self.reconnect_attempts += 1
            logger.error(f"❌ Ошибка подключения (попытка {self.reconnect_attempts}): {e}")
            return False
    
    async def disconnect(self):
        """Отключение от голосового канала"""
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
            self.voice_client = None
            self.is_connected = False
            logger.info("🔇 Отключился от голосового канала")
    
    async def ensure_connection(self, guild):
        """
        Проверка и восстановление соединения
        guild - объект сервера Discord
        """
        target_channel = bot.get_channel(self.target_channel_id)
        
        if not target_channel:
            logger.error(f"❌ Канал с ID {self.target_channel_id} не найден!")
            return
        
        if target_channel.guild.id != guild.id:
            return  # Это не наш сервер
        
        # Получаем текущее голосовое подключение
        voice_client = guild.voice_client
        
        # Если нет подключения или оно разорвано
        if not voice_client or not voice_client.is_connected():
            # Пытаемся подключиться
            if self.reconnect_attempts < self.max_attempts:
                await self.connect_to_channel(target_channel)
            else:
                logger.warning(f"⚠️ Достигнут лимит попыток подключения")
        
        # Если подключено, но не в том канале
        elif voice_client.channel.id != self.target_channel_id:
            try:
                await voice_client.move_to(target_channel)
                logger.info(f"🔄 Перемещен в {target_channel.name}")
            except Exception as e:
                logger.error(f"❌ Ошибка перемещения: {e}")

# Создаем экземпляр менеджера голоса
voice_manager = VoiceManager()

# ========== СОБЫТИЯ БОТА ==========

@bot.event
async def on_ready():
    """Срабатывает, когда бот запустился"""
    
    logger.info(f'🤖 Бот {bot.user.name} запущен!')
    logger.info(f'🆔 ID бота: {bot.user.id}')
    logger.info(f'📡 Серверы: {", ".join([g.name for g in bot.guilds])}')
    logger.info(f'🎯 Целевой канал ID: {VOICE_CHANNEL_ID}')
    
    # Устанавливаем статус бота
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!help | Голосовой бот"
        )
    )
    
    # Подключаемся к голосовому каналу
    for guild in bot.guilds:
        await voice_manager.ensure_connection(guild)
    
    # Запускаем фоновую задачу для поддержания соединения
    if not maintain_connection.is_running():
        maintain_connection.start()

@tasks.loop(seconds=30)
async def maintain_connection():
    """Фоновая задача для поддержания соединения (запускается каждые 30 секунд)"""
    for guild in bot.guilds:
        await voice_manager.ensure_connection(guild)

@maintain_connection.before_loop
async def before_maintain_connection():
    """Ждем, пока бот полностью запустится, перед запуском фоновой задачи"""
    await bot.wait_until_ready()

@bot.event
async def on_voice_state_update(member, before, after):
    """Срабатывает при изменении голосового состояния"""
    
    # Проверяем, изменилось ли состояние самого бота
    if member == bot.user:
        if after.channel is None:
            # Бот отключился от канала
            logger.warning(f"⚠️ Бот отключен от {before.channel.name if before.channel else 'неизвестного канала'}")
            voice_manager.is_connected = False
            voice_manager.voice_client = None
        else:
            # Бот подключился к каналу
            logger.info(f"✅ Бот в канале: {after.channel.name}")
            voice_manager.is_connected = True

@bot.event
async def on_command_error(ctx, error):
    """Обработка ошибок команд"""
    
    if isinstance(error, commands.CommandNotFound):
        # Команда не найдена - игнорируем
        pass
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ У вас нет прав для этой команды!")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Неверный формат аргумента!")
    else:
        logger.error(f"Ошибка команды: {error}")
        await ctx.send(f"❌ Произошла ошибка: {error}")

# ========== КОМАНДЫ БОТА ==========

@bot.command(name='help')
async def help_command(ctx):
    """Команда !help - показывает список команд"""
    
    # Создаем красивое встраиваемое сообщение
    embed = discord.Embed(
        title="🤖 Голосовой бот - команды",
        description="Вот что я умею:",
        color=discord.Color.blue()  # синий цвет
    )
    
    # Добавляем поля с командами
    embed.add_field(
        name="!join",
        value="Подключиться к вашему голосовому каналу",
        inline=False
    )
    
    embed.add_field(
        name="!leave",
        value="Отключиться от голосового канала",
        inline=False
    )
    
    embed.add_field(
        name="!status",
        value="Показать статус подключения",
        inline=False
    )
    
    embed.add_field(
        name="!ping",
        value="Проверить задержку бота",
        inline=True
    )
    
    embed.add_field(
        name="!move [название]",
        value="Переместить в другой канал (например !move Общий)",
        inline=True
    )
    
    # Добавляем подвал с информацией
    embed.set_footer(text=f"Запросил: {ctx.author.name}")
    
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping_command(ctx):
    """Команда !ping - проверка задержки"""
    
    latency = round(bot.latency * 1000)  # задержка в миллисекундах
    await ctx.send(f"🏓 Понг! Задержка: {latency}ms")

@bot.command(name='join')
async def join_command(ctx):
    """Команда !join - подключение к голосовому каналу пользователя"""
    
    # Проверяем, в голосовом ли канале пользователь
    if not ctx.author.voice:
        await ctx.send("❌ Вы должны находиться в голосовом канале!")
        return
    
    # Получаем канал пользователя
    channel = ctx.author.voice.channel
    
    # Подключаемся
    success = await voice_manager.connect_to_channel(channel)
    
    if success:
        await ctx.send(f"✅ Подключился к **{channel.name}**")
    else:
        await ctx.send(f"❌ Не удалось подключиться к {channel.name}")

@bot.command(name='leave')
async def leave_command(ctx):
    """Команда !leave - отключение от голосового канала"""
    
    if ctx.voice_client:
        await voice_manager.disconnect()
        await ctx.send("🔇 Отключился от голосового канала")
    else:
        await ctx.send("❌ Я не в голосовом канале!")

@bot.command(name='status')
async def status_command(ctx):
    """Команда !status - показывает статус бота"""
    
    # Создаем сообщение со статусом
    embed = discord.Embed(
        title="📊 Статус бота",
        color=discord.Color.green() if voice_manager.is_connected else discord.Color.red()
    )
    
    # Текущий канал
    if ctx.voice_client:
        channel = ctx.voice_client.channel
        embed.add_field(
            name="🎵 Текущий канал",
            value=f"{channel.name} (ID: {channel.id})",
            inline=False
        )
    else:
        embed.add_field(
            name="🎵 Текущий канал",
            value="Не подключен",
            inline=False
        )
    
    # Целевой канал
    target = bot.get_channel(VOICE_CHANNEL_ID)
    if target:
        embed.add_field(
            name="🎯 Целевой канал",
            value=f"{target.name} (ID: {target.id})",
            inline=False
        )
    else:
        embed.add_field(
            name="🎯 Целевой канал",
            value=f"ID: {VOICE_CHANNEL_ID} (не найден)",
            inline=False
        )
    
    # Задержка
    embed.add_field(
        name="⏱️ Задержка",
        value=f"{round(bot.latency * 1000)}ms",
        inline=True
    )
    
    await ctx.send(embed=embed)

@bot.command(name='move')
async def move_command(ctx, *, channel_name: str = None):
    """Команда !move название_канала - перемещение в другой канал"""
    
    if not channel_name:
        await ctx.send("❌ Укажите название канала! Пример: !move Общий")
        return
    
    # Ищем канал по названию
    found_channel = None
    for channel in ctx.guild.voice_channels:
        if channel_name.lower() in channel.name.lower():
            found_channel = channel
            break
    
    if not found_channel:
        await ctx.send(f"❌ Канал '{channel_name}' не найден!")
        return
    
    # Перемещаемся
    success = await voice_manager.connect_to_channel(found_channel)
    
    if success:
        await ctx.send(f"✅ Переместился в **{found_channel.name}**")
    else:
        await ctx.send(f"❌ Не удалось переместиться в {found_channel.name}")

@bot.command(name='say')
async def say_command(ctx, *, text: str = None):
    """Команда !say текст - бот говорит текст (только если в голосовом канале)"""
    
    if not text:
        await ctx.send("❌ Укажите текст! Пример: !say Привет")
        return
    
    if not ctx.voice_client:
        await ctx.send("❌ Я не в голосовом канале!")
        return
    
    # Здесь можно добавить синтез речи, но для простоты просто отправляем сообщение
    await ctx.send(f"🔊 Я бы сказал: {text}")

# ========== ЗАПУСК БОТА ==========

if __name__ == "__main__":
    try:
        logger.info("🚀 Запуск бота...")
        bot.run(TOKEN)
    except discord.LoginFailure:
        logger.error("❌ Ошибка входа! Проверьте токен в файле .env")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        