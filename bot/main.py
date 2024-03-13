import io
import csv


# from dotenv import load_dotenv
import os

# load_dotenv()

import psycopg2

DB_NAME = os.environ['POSTGRES_DB'] 
DB_USER = os.environ['POSTGRES_USER'] 
DB_PASSWORD = os.environ['POSTGRES_PASSWORD'] 
DB_HOST =  'db' #'127.0.0.1'
DB_PORT =  '5432'#'25432'

BOT_ADMIN_USER_ID=int(os.environ['BOT_ADMIN_USER_ID'])
BOT_API_TOKEN=os.environ['BOT_API_TOKEN']


from redis_utils import enqueue_photo, dequeue_photo, get_queue_length, peek_photo

# aiogram==2.25.1
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.types import InputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
# from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command, Text
# from aiogram.dispatcher.filters.state import State, StatesGroup
# from aiogram.utils import executor

from datetime import datetime

API_TOKEN = BOT_API_TOKEN  # Замените на свой токен

# Инициализация базы данных
conn = psycopg2.connect(
    database=DB_NAME,
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    port=DB_PORT
)

cursor = conn.cursor()


create_table_command = 'CREATE TABLE IF NOT EXISTS like_history (id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, datestamp TIMESTAMP);'
cursor.execute(create_table_command)
conn.commit()

create_table_command = 'CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, username TEXT, first_name TEXT);'
cursor.execute(create_table_command)
conn.commit()


# function for inserting or updating data in "users" table. If there is no user_id in table, it will be inserted. If there is, it will be updated, but only if new data is fuller that old
def store_user(user_id, username, first_name):
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (str(user_id),))
    row = cursor.fetchone()
    if row:
        new_username = username if username else row[1]
        new_first_name = first_name if first_name else row[2]
        cursor.execute("UPDATE users SET username = %s, first_name = %s WHERE user_id = %s", (new_username, new_first_name, str(user_id)))
    else:
        cursor.execute("INSERT INTO users (user_id, username, first_name) VALUES (%s, %s, %s)", (str(user_id), username, first_name))
    conn.commit()


# function to select all users
def select_all_users():
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    return rows



# function for inserting data in like_history table in database, arguments: user_id, photo_unique_id. id and datestamp are generated automatically
def insert_like_history(user_id):
    cursor.execute("INSERT INTO like_history (user_id, datestamp) VALUES (%s, %s)", (str(user_id), datetime.now()))
    conn.commit()

# function to select all from like_history table
def select_all():
    cursor.execute("SELECT * FROM like_history")
    rows = cursor.fetchall()
    return rows

# function to delete all from like_history table
def delete_all():
    cursor.execute("DELETE FROM like_history")
    conn.commit()

# funtion to get number of rows that have user_id equals some user_id
def get_count(user_id):
    cursor.execute("SELECT COUNT(*) FROM like_history WHERE user_id = %s", (str(user_id),))
    count = cursor.fetchone()[0]
    return count




#Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


def add_user(message: Message):
    user_id = message.from_user['id'],
    try:
        first_name = message.from_user['first_name']
    except:
        first_name = ''
    try:
        username = message.from_user['username']
    except:
        username = ''
    store_user(user_id, username, first_name)
    
    


not_admin_message = '''Отправь сюда фотографию, если считаешь, что она может подойти для стикерпака, который делает Артём Прохоров: \n\nhttps://t.me/addstickers/so_v24\n\nЕсли твоя фотография окажется классной, я это запомню! Топ отправителей хороших фотографий будут получать некоторые прикольные плюшки :)'''
@dp.message_handler(Command("start"))
async def handle_start_command(message: Message):
    if message.from_user.id != BOT_ADMIN_USER_ID:
        add_user(message)
        await bot.send_message(chat_id=message.from_user.id, text=not_admin_message)
        await bot.send_sticker(message.from_user.id,'CAACAgIAAxkBAAPmZfDu5_I4PQUVOUa-6FCXIPM2068AAp5GAAKSnXBLVyxxOfppIE40BA')
    else:
        reply_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = [types.KeyboardButton(text="👍"), types.KeyboardButton(text="👎")]
        reply_keyboard.add(*buttons)
        await message.answer("Привет! Вот команды для тебя: \n\n Проверить очередь: /queue \n\n Сделать дамп: /dump", reply_markup=reply_keyboard)


@dp.message_handler(Command("queue"))
async def handle_queue_command(message: Message):
    if message.from_user.id != BOT_ADMIN_USER_ID:
        return
    photo_data = peek_photo()
    if photo_data:
        await bot.send_message(BOT_ADMIN_USER_ID, f"В очереди {get_queue_length()} фотографий, вот первая из них:")
        await bot.forward_message(BOT_ADMIN_USER_ID, photo_data['user_id'], photo_data['message_id'])
    else:
        await bot.send_message(BOT_ADMIN_USER_ID, "В очереди нет фотографий")


@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_photo(message: types.Message):
    # Сохраняем информацию о фото в базу данных
    user_id = message.from_user.id
    photo_unique_id = message.photo[-1].file_unique_id
    enqueue_photo(user_id, message.message_id, photo_unique_id)
    await bot.send_message(message.from_user.id, "Фото отправлено Артёму, спасибо!")

    await bot.send_message(BOT_ADMIN_USER_ID, f"В очереди {get_queue_length()} фотографий, вот первая из них:")
    photo_data = peek_photo()
    if photo_data:
        await bot.forward_message(BOT_ADMIN_USER_ID, photo_data['user_id'], photo_data['message_id'])

    
@dp.message_handler(Text(equals="👍"))
async def handle_like(message: types.Message):
    user_id = message.from_user.id
    if user_id != BOT_ADMIN_USER_ID:
        return
    photo_data = dequeue_photo()
    if not photo_data:
        await bot.send_message(BOT_ADMIN_USER_ID, "В очереди нет фотографий")
        return
    insert_like_history(photo_data['user_id'])
    await bot.send_message(BOT_ADMIN_USER_ID, "Лайк добавлен!")
    photo_user_id = photo_data['user_id']
    sms = f''
    await bot.send_message(photo_user_id, 'Артём Прохоров оценил ваше фото:')
    try:
        await bot.forward_message(photo_data['user_id'], photo_data['user_id'], photo_data['message_id'])
    except:
        pass
    await bot.send_message(photo_user_id,'Всего ты отравил(а) хороших фоток: ' + str(get_count(photo_user_id)))
    photo_data = peek_photo()
    if photo_data:
        try:
            await bot.forward_message(BOT_ADMIN_USER_ID, photo_data['user_id'], photo_data['message_id'])
        except:
            await bot.send_message(BOT_ADMIN_USER_ID, "Произошла ошибка. Нажми /queue")
            dequeue_photo()
    else:
        await bot.send_message(BOT_ADMIN_USER_ID, "В очереди больше нет фотографий")



@dp.message_handler(Text(equals="👎"))
async def handle_dis(message: types.Message):
    user_id = message.from_user.id
    if user_id != BOT_ADMIN_USER_ID:
        return
    photo_data = dequeue_photo()
    if not photo_data:
        await bot.send_message(BOT_ADMIN_USER_ID, "В очереди нет фотографий")
        return
    await bot.send_message(BOT_ADMIN_USER_ID, "Фото отмечено как не очень понравившееся")

    photo_data = peek_photo()
    if photo_data:
        try:
            await bot.forward_message(BOT_ADMIN_USER_ID, photo_data['user_id'], photo_data['message_id'])
        except:
            await bot.send_message(BOT_ADMIN_USER_ID, "Произошла ошибка. Нажми /queue")
            dequeue_photo()
            
    else:
        await bot.send_message(BOT_ADMIN_USER_ID, "В очереди больше нет фотографий")




@dp.message_handler(Command("dump"))
async def handle_test(message: types.Message):
    if message.from_user.id != BOT_ADMIN_USER_ID:
        return
    
    likes_history = select_all()

    csv_content = io.StringIO()
    csv_writer = csv.writer(csv_content)
    csv_writer.writerow(['id', 'user_id', 'datestamp'])
    for like in likes_history:
        csv_writer.writerow([like[0], like[1], like[2]])
    csv_content.seek(0)
    await bot.send_document(BOT_ADMIN_USER_ID, InputFile(csv_content, filename="likes_history.csv"), caption="История лайков")


    users = select_all_users()
    csv_content = io.StringIO()
    csv_writer = csv.writer(csv_content)
    csv_writer.writerow(['user_id', 'username', 'first_name'])
    for user in users:
        csv_writer.writerow([user[0], user[1], user[2]])
    csv_content.seek(0)
    await bot.send_document(BOT_ADMIN_USER_ID, InputFile(csv_content, filename="users.csv"), caption="Пользователи")


if __name__ == '__main__':
    from aiogram import executor

    executor.start_polling(dp, skip_updates=False)