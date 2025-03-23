import telebot
import sqlite3
from telebot import types
import re
from config import TOKEN

# Токен
bot = telebot.TeleBot(TOKEN)

# Создаем DB
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц базы
cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    name_categories TEXT
                )''')
cursor.execute('''CREATE TABLE IF NOT EXISTS subcategories (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER,
                    name_subcategories TEXT
                )''')
cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    admin_name TEXT
                )''')
cursor.execute('''CREATE TABLE IF NOT EXISTS links (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER,
                    subcategory_id INTEGER,
                    name TEXT,
                    url TEXT,
                    FOREIGN KEY (category_id) REFERENCES categories(ID),
                    FOREIGN KEY (subcategory_id) REFERENCES subcategories(ID)
                )''')
cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_run BOOLEAN,
                    start_text TEXT
                )''')

# Проверяем наличие записи в таблице settings, чтобы понять, запускался ли бот ранее
cursor.execute("SELECT * FROM settings")
settings_data = cursor.fetchone()  # получение записей из таблицы settings

if settings_data is None:  # проверка наличия записей
    cursor.execute(
        "INSERT INTO settings (first_run, start_text) VALUES (?, ?)",
        (True,
         "Привет! этот текст можно поменять на необходимый в настройках администратора"
         ))
    conn.commit()


@bot.message_handler(commands=['set_start_text'])
def set_start_text(message):
    cursor.execute("SELECT * FROM admins WHERE admin_id=?",
                   (message.from_user.id, ))
    admin_data = cursor.fetchone()

    if admin_data:
        bot.send_message(message.chat.id,
                         "Введите новый текст для команды /start:")
        bot.register_next_step_handler(message, process_start_text)
    else:
        bot.send_message(message.chat.id,
                         "У вас нет прав для выполнения этой команды.")


def process_start_text(message):
    new_start_text = message.text.strip()
    cursor.execute("UPDATE settings SET start_text=?", (new_start_text, ))
    conn.commit()
    bot.send_message(message.chat.id,
                     "Текст для команды /start успешно изменен.")


@bot.message_handler(commands=['start'])
def start(message):
    cursor.execute("SELECT * FROM settings")
    settings_data = cursor.fetchone()

    if settings_data and settings_data[1]:  # Если first_run == True
        bot.reply_to(
            message,
            "Привет, ты первый пользователь бота. Пожалуйста, представься.",
            disable_notification=True)
        bot.register_next_step_handler(message, process_name_step)
    else:
        # Выводим приветственное сообщение
        if settings_data and settings_data[2]:  # Если есть start_text
            bot.reply_to(message, settings_data[2], disable_notification=True)
        else:
            bot.reply_to(message,
                         "Добро пожаловать!",
                         disable_notification=True)

        # Получаем все категории
        cursor.execute("SELECT * FROM categories")
        categories_data = cursor.fetchall()

        if categories_data:  # Если есть категории
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            for category in categories_data:
                # Добавляем кнопку с названием категории
                keyboard.add(
                    types.InlineKeyboardButton(
                        text=category[1],
                        callback_data=f"category_{category[0]}"))
            bot.send_message(message.chat.id,
                             "Выберите категорию:",
                             reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id,
                             "К сожалению, пока нет доступных категорий.",
                             disable_notification=True)


def process_name_step(message):
    name = message.text
    cursor.execute("SELECT * FROM settings")
    settings_data = cursor.fetchone()
    cursor.execute("INSERT INTO admins (admin_id, admin_name) VALUES (?, ?)",
                   (message.from_user.id, name))
    cursor.execute("UPDATE settings SET first_run = ? WHERE ID = ?",
                   (False, settings_data[0]))
    conn.commit()
    bot.send_message(
        message.chat.id, f"Теперь вы администратор бота, {name}!\n"
        f"Команда /panel запустит админ-панель")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('category_'))
def show_subcategories(call):
    category_id = call.data.split("_")[1]  # Получаем ID категории
    bot.delete_message(call.message.chat.id,
                       call.message.message_id)  # Удаляем предыдущее сообщение

    # Получаем подкатегории для выбранной категории
    cursor.execute("SELECT * FROM subcategories WHERE category_id=?",
                   (category_id, ))
    subcategories_data = cursor.fetchall()

    if subcategories_data:  # Если есть подкатегории
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for subcategory in subcategories_data:
            # Добавляем кнопку с названием подкатегории
            keyboard.add(
                types.InlineKeyboardButton(
                    text=subcategory[2],
                    callback_data=f"subcategory_{subcategory[0]}"))
        bot.send_message(call.message.chat.id,
                         "Выберите подкатегорию:",
                         reply_markup=keyboard)
    else:
        bot.send_message(call.message.chat.id,
                         "В этой категории пока нет подкатегорий.",
                         disable_notification=True)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('subcategory_'))
def show_links(call):
    subcategory_id = call.data.split("_")[1]  # Получаем ID подкатегории
    bot.delete_message(call.message.chat.id,
                       call.message.message_id)  # Удаляем предыдущее сообщение

    # Получаем ссылки для выбранной подкатегории
    cursor.execute("SELECT * FROM links WHERE subcategory_id=?",
                   (subcategory_id, ))
    links_data = cursor.fetchall()

    if links_data:  # Если есть ссылки
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for link in links_data:
            # Добавляем кнопку с названием ссылки и URL
            keyboard.add(types.InlineKeyboardButton(text=link[3], url=link[4]))
        bot.send_message(call.message.chat.id,
                         "Выберите ссылку:",
                         reply_markup=keyboard)
    else:
        bot.send_message(call.message.chat.id,
                         "В этой подкатегории пока нет ссылок.",
                         disable_notification=True)


@bot.message_handler(commands=['panel'])
def admin_panel(message):
    cursor.execute("SELECT * FROM admins WHERE admin_id=?",
                   (message.from_user.id, ))
    admin_data = cursor.fetchone()

    if admin_data:
        bot.send_message(
            message.chat.id, f"Панель администратора\n"
            f"/admin - Добавление/удаление администраторов бота\n"
            f"/set_start_text - Изменить приветственное сообщение для бота\n"
            f"/categories - Настройка категорий\n"
            f"/subcategories - Настройка вопросов внутри категорий\n"
            f"/links - Добавление ссылок\n"
            f"",
            disable_notification=True)
    else:
        bot.send_message(message.chat.id,
                         "У вас нет прав для выполнения этой команды.")


@bot.message_handler(commands=[
    'getmyid'
])  # получение id. Понадобится для добавления новых администраторов
def get_user_id(message):
    bot.reply_to(
        message,
        f"Ваш Telegram ID: {message.from_user.id}. \nПожалуйста, передайте это сообщение администратору.",
        disable_notification=True)


@bot.message_handler(commands=['categories'])
def categories_panel(message):
    # Проверяем, является ли пользователь администратором
    cursor.execute("SELECT * FROM admins WHERE admin_id=?",
                   (message.from_user.id, ))
    admin_data = cursor.fetchone()

    if admin_data:
        cursor.execute("SELECT * FROM categories")
        categories = cursor.fetchall()

        keyboard = types.InlineKeyboardMarkup()

        if categories:
            for category in categories:
                button = types.InlineKeyboardButton(
                    category[1], callback_data=f"show_category:{category[0]}")
                keyboard.add(button)
        else:
            bot.send_message(message.chat.id, "Нет категорий.")

        add_button = types.InlineKeyboardButton("✅ Добавить",
                                                callback_data="add_category")
        keyboard.add(add_button)

        bot.send_message(message.chat.id,
                         "Список категорий:",
                         reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id,
                         "У вас нет прав для выполнения этой команды.")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('show_category:'))
def show_category_info(call):
    category_id = call.data.split(":")[1]

    cursor.execute("SELECT * FROM categories WHERE ID=?", (category_id, ))
    category_data = cursor.fetchone()

    if category_data:
        category_name = category_data[1]

        keyboard = types.InlineKeyboardMarkup()
        delete_button = types.InlineKeyboardButton(
            "❌ Удалить", callback_data=f"delete_category:{category_id}")
        rename_button = types.InlineKeyboardButton(
            "✏️ Переименовать", callback_data=f"rename_category:{category_id}")
        keyboard.add(delete_button, rename_button)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id,
                         f"Название категории: {category_name}",
                         reply_markup=keyboard)
    else:
        bot.send_message(call.message.chat.id, "Категория не найдена.")


@bot.callback_query_handler(func=lambda call: call.data == 'add_category')
def add_category(call):
    bot.send_message(call.message.chat.id, "Введите название новой категории:")
    bot.register_next_step_handler(call.message, process_category_name)


def process_category_name(message):
    category_name = message.text.strip()
    cursor.execute("INSERT INTO categories (name_categories) VALUES (?)",
                   (category_name, ))
    conn.commit()
    bot.send_message(message.chat.id,
                     f"Категория '{category_name}' успешно добавлена.")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('delete_category:'))
def delete_category(call):
    category_id = call.data.split(":")[1]

    # Проверяем, есть ли записи в subcategories для данной категории
    cursor.execute("SELECT * FROM subcategories WHERE category_id=?",
                   (category_id, ))
    subcategories = cursor.fetchall()

    if subcategories:
        bot.answer_callback_query(
            call.id, text="Невозможно удалить категорию, она не пуста!")
    else:
        # Удаляем категорию, если в ней нет записей вопросов
        cursor.execute("DELETE FROM categories WHERE ID=?", (category_id, ))
        conn.commit()
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, text="Категория успешно удалена.")
        bot.send_message(call.message.chat.id,
                         "Можно вернуться в список /categories")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('rename_category:'))
def rename_category(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    category_id = call.data.split(":")[1]
    bot.send_message(
        call.message.chat.id,
        f"Введите новое название для категории с ID {category_id}:")
    bot.register_next_step_handler(call.message, process_new_category_name,
                                   category_id)


def process_new_category_name(message, category_id):
    new_category_name = message.text.strip()

    cursor.execute("UPDATE categories SET name_categories=? WHERE ID=?",
                   (new_category_name, category_id))
    conn.commit()

    bot.reply_to(
        message,
        f"Название категории успешно изменено на '{new_category_name}'.",
        disable_notification=True)


@bot.message_handler(commands=['subcategories'])
def subcategories_panel(message):
    cursor.execute("SELECT * FROM admins WHERE admin_id=?",
                   (message.from_user.id, ))
    admin_data = cursor.fetchone()

    if admin_data:
        cursor.execute("SELECT * FROM categories")
        categories = cursor.fetchall()

        if categories:
            keyboard = types.InlineKeyboardMarkup()
            for category in categories:
                button = types.InlineKeyboardButton(
                    category[1],
                    callback_data=f"show_subcategories:{category[0]}")
                keyboard.add(button)
            bot.send_message(message.chat.id,
                             "Выберите категорию:",
                             reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id,
                             "Создайте хотя бы одну категорию.")
    else:
        bot.send_message(message.chat.id,
                         "У вас нет прав для выполнения этой команды.")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('show_subcategories:'))
def show_subcategories(call):
    category_id = call.data.split(":")[1]
    bot.delete_message(call.message.chat.id, call.message.message_id)
    cursor.execute("SELECT * FROM subcategories WHERE category_id=?",
                   (category_id, ))
    subcategories = cursor.fetchall()

    keyboard = types.InlineKeyboardMarkup()

    if subcategories:  # Если есть вопросы
        for subcategory in subcategories:
            button = types.InlineKeyboardButton(
                subcategory[2],
                callback_data=
                f"show_subcategory:{subcategory[0]}:{subcategory[1]}")
            keyboard.add(button)
    else:
        bot.send_message(call.message.chat.id,
                         "Создайте хотя бы одну подкатегорию.")

    add_button = types.InlineKeyboardButton(
        "✅ Добавить", callback_data=f"add_subcategory:{category_id}")
    keyboard.add(add_button)

    bot.send_message(call.message.chat.id,
                     "Выберите подкатегорию:",
                     reply_markup=keyboard)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('show_subcategory:'))
def show_subcategory(call):
    subcategory_id = call.data.split(":")[1]

    cursor.execute("SELECT * FROM subcategories WHERE ID=?",
                   (subcategory_id, ))
    category_data = cursor.fetchone()

    if category_data:
        category_name = category_data[2]

        keyboard = types.InlineKeyboardMarkup()
        delete_button = types.InlineKeyboardButton(
            "❌ Удалить", callback_data=f"delete_subcategory:{subcategory_id}")
        rename_button = types.InlineKeyboardButton(
            "✏️ Переименовать",
            callback_data=f"rename_subcategory:{subcategory_id}")
        keyboard.add(delete_button, rename_button)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id,
                         f"Название подкатегории: {category_name}",
                         reply_markup=keyboard)
    else:
        bot.send_message(call.message.chat.id, "Подкатегория не найдена.")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('delete_subcategory:'))
def delete_subcategory(call):
    subcategory_id = call.data.split(":")[1]

    # Проверяем, есть ли записи в subcategories для данной категории
    cursor.execute("SELECT * FROM links WHERE subcategory_id=?",
                   (subcategory_id, ))
    links = cursor.fetchall()

    if links:
        bot.answer_callback_query(
            call.id, text="Невозможно удалить подкатегорию, она не пуста!")
    else:
        # Удаляем категорию, если в ней нет записей вопросов
        cursor.execute("DELETE FROM subcategories WHERE ID=?",
                       (subcategory_id, ))
        conn.commit()
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id,
                                  text="Подкатегория успешно удалена.")
        bot.send_message(call.message.chat.id,
                         "Можно вернуться в список /subcategories")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('rename_subcategory:'))
def rename_subcategory(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    subcategory_id = call.data.split(":")[1]
    bot.send_message(
        call.message.chat.id,
        f"Введите новое название для подкатегории с ID {subcategory_id}:")
    bot.register_next_step_handler(call.message, process_new_subcategory_name,
                                   subcategory_id)


def process_new_subcategory_name(message, subcategory_id):
    new_subcategory_name = message.text.strip()

    cursor.execute("UPDATE subcategories SET name_subcategories=? WHERE ID=?",
                   (new_subcategory_name, subcategory_id))
    conn.commit()

    bot.reply_to(
        message,
        f"Название категории успешно изменено на '{new_subcategory_name}'.",
        disable_notification=True)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('add_subcategory:'))
def add_subcategory(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    category_id = call.data.split(":")[1]
    bot.send_message(call.message.chat.id, "Введите название подкатегории:")
    bot.register_next_step_handler(call.message, process_subcategory,
                                   category_id)


def process_subcategory(message, category_id):
    name_subcategories = message.text.strip()
    cursor.execute(
        "INSERT INTO subcategories (name_subcategories, category_id) VALUES (?, ?)",
        (name_subcategories, category_id))
    conn.commit()
    bot.send_message(message.chat.id, "Подкатегория успешно добавлена.")


@bot.message_handler(commands=['links'])
def links_panel(message):
    cursor.execute("SELECT * FROM admins WHERE admin_id=?",
                   (message.from_user.id, ))
    admin_data = cursor.fetchone()

    if admin_data:
        cursor.execute("SELECT * FROM categories")
        categories = cursor.fetchall()

        if categories:
            keyboard = types.InlineKeyboardMarkup()
            for category in categories:
                button = types.InlineKeyboardButton(
                    category[1],
                    callback_data=f"show_subcategories1:{category[0]}")
                keyboard.add(button)
            bot.send_message(message.chat.id,
                             "Выберите категорию:",
                             reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id,
                             "Создайте хотя бы одну категорию.")
    else:
        bot.send_message(message.chat.id,
                         "У вас нет прав для выполнения этой команды.")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('show_subcategories1:'))
def show_subcategories1(call):
    category_id = call.data.split(":")[1]
    bot.delete_message(call.message.chat.id, call.message.message_id)
    cursor.execute("SELECT * FROM subcategories WHERE category_id=?",
                   (category_id, ))
    subcategories = cursor.fetchall()

    keyboard = types.InlineKeyboardMarkup()

    if subcategories:  # Если есть вопросы
        for subcategory in subcategories:
            button = types.InlineKeyboardButton(
                subcategory[2],
                callback_data=f"show_links:{subcategory[0]}:{subcategory[1]}")
            keyboard.add(button)
        bot.send_message(call.message.chat.id,
                         "Выберите подкатегорию:",
                         reply_markup=keyboard)
    else:
        bot.send_message(call.message.chat.id,
                         "Создайте хотя бы одну подкатегорию.")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('show_links:'))
def show_links(call):
    subcategory_id = call.data.split(":")[1]
    bot.delete_message(call.message.chat.id, call.message.message_id)
    cursor.execute("SELECT * FROM links WHERE subcategory_id=?",
                   (subcategory_id, ))
    links = cursor.fetchall()

    keyboard = types.InlineKeyboardMarkup()

    if links:  # Если есть вопросы
        for link in links:
            button = types.InlineKeyboardButton(
                link[3], callback_data=f"show_link:{link[0]}")
            keyboard.add(button)
    else:
        bot.send_message(call.message.chat.id, "Создайте хотя бы одну ссылку.")

    add_button = types.InlineKeyboardButton(
        "✅ Добавить", callback_data=f"add_link:{subcategory_id}")
    keyboard.add(add_button)

    bot.send_message(call.message.chat.id,
                     "Выберите ссылку:",
                     reply_markup=keyboard)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('show_link:'))
def show_link(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    link_id = call.data.split(":")[1]

    cursor.execute("SELECT * FROM links WHERE ID=?", (link_id, ))
    link_data = cursor.fetchone()

    if link_data:
        link_name = link_data[3]

        keyboard = types.InlineKeyboardMarkup()
        delete_button = types.InlineKeyboardButton(
            "❌ Удалить", callback_data=f"delete_link:{link_id}")
        rename_button = types.InlineKeyboardButton(
            "✏️ Переименовать", callback_data=f"rename_link:{link_id}")
        keyboard.add(delete_button, rename_button)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id,
                         f"Название ссылки: {link_name}",
                         reply_markup=keyboard)
    else:
        bot.send_message(call.message.chat.id, "Ссылка не найдена.")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('rename_link:'))
def rename_link(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    link_id = call.data.split(":")[1]
    bot.send_message(call.message.chat.id,
                     f"Введите новое название для ссылки с ID {link_id}:")
    bot.register_next_step_handler(call.message, process_new_link_name,
                                   link_id)


def process_new_link_name(message, link_id):
    new_link_name = message.text.strip()
    bot.send_message(message.chat.id, "Введите новый URL для ссылки:")
    bot.register_next_step_handler(message, process_new_link_url, link_id,
                                   new_link_name)


def process_new_link_url(message, link_id, new_link_name):
    new_link_url = message.text.strip()

    # Проверяем, содержит ли URL-адрес http:// или https://, если нет, добавляем https://
    if not re.match(r'https?://', new_link_url):
        new_link_url = 'https://' + new_link_url

    cursor.execute("UPDATE links SET name=?, url=? WHERE ID=?",
                   (new_link_name, new_link_url, link_id))
    conn.commit()
    bot.send_message(message.chat.id, "Ссылка успешно изменена.")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('add_link:'))
def add_link(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    subcategory_id = call.data.split(":")[1]
    bot.send_message(call.message.chat.id, "Введите имя ссылки:")
    bot.register_next_step_handler(call.message, process_link_name,
                                   subcategory_id)


def process_link_name(message, subcategory_id):
    name = message.text.strip()
    bot.send_message(message.chat.id, "Введите URL ссылки:")
    bot.register_next_step_handler(message, process_link_url, name,
                                   subcategory_id)


def process_link_url(message, name, subcategory_id):
    url = message.text.strip()

    # Проверяем, содержит ли URL-адрес http:// или https://, если нет, добавляем https://
    if not re.match(r'https?://', url):
        url = 'https://' + url

    cursor.execute(
        "INSERT INTO links (name, url, subcategory_id) VALUES (?, ?, ?)",
        (name, url, subcategory_id))
    conn.commit()
    bot.send_message(message.chat.id, "Ссылка успешно добавлена.")


@bot.message_handler(commands=['admin'])
def admin_panel(message):
    # Проверяем, является ли пользователь администратором
    cursor.execute("SELECT * FROM admins WHERE admin_id=?",
                   (message.from_user.id, ))
    admin_data = cursor.fetchone()

    if admin_data:
        cursor.execute("SELECT * FROM admins WHERE admin_id != ?",
                       (message.from_user.id, ))
        admin_list = cursor.fetchall()

        keyboard = types.InlineKeyboardMarkup()

        if admin_list:
            for admin in admin_list:
                button = types.InlineKeyboardButton(
                    admin[2], callback_data=f"show_admin:{admin[0]}")
                keyboard.add(button)

        add_button = types.InlineKeyboardButton("✅ Добавить",
                                                callback_data="add_admin")
        keyboard.add(add_button)

        if admin_list:
            bot.send_message(message.chat.id,
                             "🛡️ Список администраторов:",
                             reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id,
                             "Нет администраторов, кроме Вас.",
                             reply_markup=keyboard)

    else:
        bot.send_message(message.chat.id,
                         "У вас нет прав для выполнения этой команды.")


@bot.callback_query_handler(func=lambda call: call.data == 'add_admin')
def add_admin(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(
        call.message.chat.id,
        "Введите Telegram ID нового администратора:\n пользователь может узнать его по команде /getmyid"
    )
    admin_adding_process[call.from_user.id] = True


@bot.message_handler(func=lambda message: True)
def process_admin_id(message):
    if message.from_user.id in admin_adding_process and admin_adding_process[
            message.from_user.id]:
        try:
            admin_id = int(message.text.strip())
            cursor.execute("SELECT * FROM admins WHERE admin_id=?",
                           (admin_id, ))
            existing_admin = cursor.fetchone()
            if existing_admin:
                bot.reply_to(message,
                             "Администратор с таким ID уже существует.",
                             disable_notification=True)
            else:
                bot.send_message(message.chat.id,
                                 "Введите имя нового администратора:")
                bot.register_next_step_handler(message, process_admin_name,
                                               admin_id)
        except ValueError:
            bot.reply_to(message,
                         "Некорректный формат Telegram ID.",
                         disable_notification=True)
    else:
        pass


def process_admin_name(message, admin_id):
    admin_name = message.text.strip()
    cursor.execute("INSERT INTO admins (admin_id, admin_name) VALUES (?, ?)",
                   (admin_id, admin_name))
    conn.commit()
    bot.reply_to(message,
                 f"Администратор {admin_name} успешно добавлен.",
                 disable_notification=True)
    admin_adding_process[message.from_user.id] = False


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('show_admin:'))
def show_admin_info(call):
    admin_id = int(call.data.split(":")[1])

    cursor.execute("SELECT * FROM admins WHERE ID=?", (admin_id, ))
    admin_data = cursor.fetchone()

    if admin_data:
        admin_id = admin_data[1]
        admin_name = admin_data[2]

        keyboard = types.InlineKeyboardMarkup()
        delete_button = types.InlineKeyboardButton(
            "❌ Удалить", callback_data=f"delete_admin:{admin_id}")
        keyboard.add(delete_button)

        bot.send_message(call.message.chat.id,
                         f"ID администратора: {admin_id}\nИмя: {admin_name}",
                         reply_markup=keyboard)
    else:
        bot.send_message(call.message.chat.id, "Администратор не найден.")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('delete_admin:'))
def delete_admin(call):
    admin_id = int(call.data.split(":")[1])

    cursor.execute("DELETE FROM admins WHERE admin_id=?", (admin_id, ))
    conn.commit()

    bot.answer_callback_query(call.id, text="Администратор успешно удален.")
    bot.send_message(call.message.chat.id, f"Можно вернуться в список /admin")


bot.polling()
