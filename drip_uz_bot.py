import requests
import time
import sqlite3
from datetime import datetime, timedelta
import os
import asyncio
from telegram.ext import Application

async def main():
    application = Application.builder().token(os.environ['BOT_TOKEN']).build()
    
    # Твоя существующая логика бота
    
    # Для Render используй polling (проще)
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
BOT_TOKEN = "8068431876:AAFcbX4emihCok_tDu-ZcmsCqd6fAwveyl0"
CREATOR_ID = 7392649768

# Состояния пользователей (user_id -> состояние)
user_states = {}

# База данных
def init_db():
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            nickname TEXT,
            rank TEXT DEFAULT 'moderator',
            registered_date TEXT,
            total_orders INTEGER DEFAULT 0,
            successful_orders INTEGER DEFAULT 0,
            rating REAL DEFAULT 5.0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            start_time TEXT,
            last_activity TEXT,
            chat_type TEXT DEFAULT 'question',
            status TEXT DEFAULT 'active'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            admin_id INTEGER,
            order_details TEXT,
            status TEXT DEFAULT 'new',
            created_date TEXT,
            updated_date TEXT,
            admin_notes TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_number TEXT,
            card_holder TEXT,
            bank_name TEXT
        )
    ''')
    
    # Добавляем создателя если нет
    cursor.execute('SELECT * FROM admins WHERE user_id = ?', (CREATOR_ID,))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO admins (user_id, username, full_name, nickname, rank, registered_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (CREATOR_ID, "creator", "Creator", "Создатель", "creator", datetime.now().isoformat()))
        print("✅ Создатель добавлен в базу")
    
    # Добавляем тестовую карту
    cursor.execute('SELECT * FROM payment_cards')
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO payment_cards (card_number, card_holder, bank_name)
            VALUES (?, ?, ?)
        ''', ("8600 1234 5678 9012", "DRIP UZ", "Kapital Bank"))
    
    conn.commit()
    conn.close()
    
    print("✅ База данных инициализирована")

# Проверка прав
def is_creator(user_id):
    return user_id == CREATOR_ID

def is_admin(user_id):
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM admins WHERE user_id = ?', (user_id,))
    admin = cursor.fetchone()
    conn.close()
    return admin is not None

def get_admin_rank(user_id):
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    cursor.execute('SELECT rank FROM admins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Отправка сообщения
def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        data["reply_markup"] = reply_markup
    
    try:
        response = requests.post(url, json=data)
        return response.json()
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return None

# Получение обновлений
def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 30}
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        print(f"❌ Ошибка получения updates: {e}")
        return {"result": []}

# Клавиатуры
def get_client_keyboard():
    return {
        "keyboard": [
            [{"text": "🛍️ Заказать товар"}],
            [{"text": "📦 Наличие товара"}, {"text": "💳 Реквизиты"}],
            [{"text": "💬 Задать вопрос"}]
        ],
        "resize_keyboard": True
    }

def get_cancel_keyboard():
    return {
        "keyboard": [
            [{"text": "❌ Отменить вопрос"}]
        ],
        "resize_keyboard": True
    }

def get_admin_keyboard():
    return {
        "keyboard": [
            [{"text": "💬 Активные чаты"}, {"text": "👥 Админы"}],
            [{"text": "💳 Карты оплаты"}, {"text": "📊 Статистика"}],
            [{"text": "📦 Управление заказами"}, {"text": "📈 Аналитика"}],
        ],
        "resize_keyboard": True
    }

def get_creator_keyboard():
    return {
        "keyboard": [
            [{"text": "💬 Активные чаты"}, {"text": "👥 Админы"}],
            [{"text": "💳 Карты оплаты"}, {"text": "📊 Статистика"}],
            [{"text": "📦 Управление заказами"}, {"text": "📈 Аналитика"}],
            [{"text": "👑 Управление админами"}],
        ],
        "resize_keyboard": True
    }

def get_order_management_keyboard(order_id):
    return {
        "inline_keyboard": [
            [
                {"text": "✅ В работе", "callback_data": f"order_status_{order_id}_in_progress"},
                {"text": "💰 Ожидает оплаты", "callback_data": f"order_status_{order_id}_waiting_payment"}
            ],
            [
                {"text": "🚚 Отправлен", "callback_data": f"order_status_{order_id}_shipped"},
                {"text": "✅ Завершен", "callback_data": f"order_status_{order_id}_completed"}
            ],
            [
                {"text": "❌ Отменен", "callback_data": f"order_status_{order_id}_cancelled"},
                {"text": "📝 Заметки", "callback_data": f"order_notes_{order_id}"}
            ]
        ]
    }

def get_chat_management_keyboard(chat_id):
    return {
        "inline_keyboard": [
            [{"text": "✅ Закрыть чат", "callback_data": f"close_chat_{chat_id}"}],
            [{"text": "💬 Ответить", "callback_data": f"reply_chat_{chat_id}"}]
        ]
    }

# Обработка старта для клиентов
def handle_client_start(user_id, username, first_name):
    if user_id in user_states:
        del user_states[user_id]
    
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM chats WHERE user_id = ?', (user_id,))
    chat = cursor.fetchone()
    
    if chat and chat[0] == 'closed':
        cursor.execute('UPDATE chats SET status = "active", last_activity = ? WHERE user_id = ?', 
                      (datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()
        welcome = f"""👋 <b>С возвращением в DripUz!</b>

Рад снова вас видеть, {first_name}! Чем могу помочь?"""
    else:
        cursor.execute('''
            INSERT OR REPLACE INTO chats 
            (user_id, username, first_name, start_time, last_activity, status) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, datetime.now().isoformat(), datetime.now().isoformat(), 'active'))
        conn.commit()
        conn.close()
        welcome = f"""👋 <b>Добро пожаловать в DripUz!</b>

🏷️ <i>DripUz - стильная одежда из Узбекистана</i>

Привет, {first_name}! Я ваш персональный консультант.

📸 <b>Весь ассортимент смотрите в нашем канале:</b>
👉 @dripuzz

💬 <b>Выберите действие ниже ⤵️</b>"""
    
    send_message(user_id, welcome, get_client_keyboard())
    print(f"✅ Новый клиент: {first_name} (@{username}) ID: {user_id}")

# Создание заказа
def create_order(user_id, order_details, admin_id=None):
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO orders (user_id, admin_id, order_details, created_date, updated_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, admin_id, order_details, datetime.now().isoformat(), datetime.now().isoformat()))
    
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return order_id

# Обновление статуса заказа
def update_order_status(order_id, status, admin_id=None, notes=None):
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE orders 
        SET status = ?, updated_date = ?, admin_id = ?, admin_notes = ?
        WHERE id = ?
    ''', (status, datetime.now().isoformat(), admin_id, notes, order_id))
    
    # Если заказ завершен, увеличиваем счетчик успешных заказов у админа
    if status == 'completed' and admin_id:
        cursor.execute('''
            UPDATE admins 
            SET successful_orders = successful_orders + 1, 
                total_orders = total_orders + 1,
                rating = (successful_orders + 1.0) / (total_orders + 1) * 5.0
            WHERE user_id = ?
        ''', (admin_id,))
    elif admin_id:
        # Просто увеличиваем общее количество заказов
        cursor.execute('''
            UPDATE admins 
            SET total_orders = total_orders + 1,
                rating = (successful_orders + 0.0) / (total_orders + 1) * 5.0
            WHERE user_id = ?
        ''', (admin_id,))
    
    conn.commit()
    
    # Получаем информацию о заказе для уведомления клиента
    cursor.execute('SELECT user_id, status FROM orders WHERE id = ?', (order_id,))
    order_info = cursor.fetchone()
    conn.close()
    
    return order_info

# Обработка кнопок клиентов
def handle_client_button(user_id, username, first_name, text):
    print(f"🔄 Клиент {first_name} нажал: {text}")
    
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM chats WHERE user_id = ?', (user_id,))
    chat = cursor.fetchone()
    conn.close()
    
    if chat and chat[0] == 'closed':
        send_message(user_id, "❌ <b>Этот чат закрыт</b>\n\nИспользуйте /start чтобы начать новый диалог")
        return
    
    if text == "🛍️ Заказать товар":
        if user_id in user_states:
            del user_states[user_id]
            
        conn = sqlite3.connect('dripuz.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE chats SET chat_type = "order" WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        response = """🛍️ <b>Оформление заказа</b>

Отлично! Чтобы оформить заказ, <b>напишите одним сообщением:</b>

📋 <b>Информация о товаре:</b>
• Ссылку на товар из @dripuzz
• Размер
• Цвет  
• Количество

👤 <b>Ваши данные:</b>
• Имя и фамилия
• Номер телефона
• Город доставки

💬 <b>Консультант свяжется с вами для подтверждения!</b>"""
        send_message(user_id, response)
        
    elif text == "📦 Наличие товара":
        if user_id in user_states:
            del user_states[user_id]
        send_message(user_id, "📦 <b>Проверка наличия</b>\n\nНапишите название товара из @dripuzz")
        
    elif text == "💳 Реквизиты":
        if user_id in user_states:
            del user_states[user_id]
        conn = sqlite3.connect('dripuz.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM payment_cards LIMIT 1')
        card = cursor.fetchone()
        conn.close()
        if card:
            card_text = f"""💳 <b>Реквизиты для оплаты:</b>

🏦 <b>Банк:</b> {card[3]}
👤 <b>Держатель:</b> {card[2]}
🔢 <b>Номер карты:</b> <code>{card[1]}</code>"""
        else:
            card_text = "💳 Реквизиты временно недоступны"
        send_message(user_id, card_text)
        
    elif text == "💬 Задать вопрос":
        user_states[user_id] = "waiting_question"
        conn = sqlite3.connect('dripuz.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE chats SET chat_type = "question" WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        send_message(user_id, "💬 <b>Задайте ваш вопрос</b>\n\nНапишите ваш вопрос в следующем сообщении...", get_cancel_keyboard())
        
    elif text == "❌ Отменить вопрос":
        if user_id in user_states:
            del user_states[user_id]
        send_message(user_id, "❌ <b>Вопрос отменен</b>\n\nВыберите другое действие:", get_client_keyboard())

# Обработка сообщений от клиентов
def handle_client_message(user_id, username, first_name, text):
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM chats WHERE user_id = ?', (user_id,))
    chat = cursor.fetchone()
    
    if chat and chat[0] == 'closed':
        conn.close()
        send_message(user_id, "❌ <b>Этот чат закрыт</b>\n\nИспользуйте /start чтобы начать новый диалог")
        return
    
    print(f"📨 Сообщение от {first_name}: {text}")
    
    if text.startswith('/'):
        send_message(user_id, "❌ <b>Неизвестная команда</b>\n\nИспользуйте кнопки для навигации")
        return
    
    cursor.execute('UPDATE chats SET last_activity = ? WHERE user_id = ?', 
                   (datetime.now().isoformat(), user_id))
    
    # Проверяем тип чата
    cursor.execute('SELECT chat_type FROM chats WHERE user_id = ?', (user_id,))
    chat_type = cursor.fetchone()
    chat_type = chat_type[0] if chat_type else 'question'
    conn.close()
    
    if user_id in user_states and user_states[user_id] == "waiting_question":
        send_message(user_id, "✅ <b>Вопрос отправлен консультанту!</b>", get_client_keyboard())
        notify_admins_about_question(user_id, username, first_name, text)
        del user_states[user_id]
    else:
        send_message(user_id, "✅ <b>Сообщение отправлено консультанту!</b>")
        
        # Если это заказ, создаем запись в orders
        if chat_type == 'order':
            order_id = create_order(user_id, text)
            notify_admins_about_order(user_id, username, first_name, text, order_id)
        else:
            notify_admins_about_message(user_id, username, first_name, text)

# Уведомление админов о заказе
def notify_admins_about_order(client_id, username, first_name, order_details, order_id):
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM admins')
    admins = cursor.fetchall()
    conn.close()
    
    message = f"""🛍️ <b>НОВЫЙ ЗАКАЗ #{order_id}</b>

👤 <b>Клиент:</b> {first_name}
📛 <b>Username:</b> @{username if username else 'нет'}
🆔 <b>ID:</b> <code>{client_id}</code>

📋 <b>Детали заказа:</b>
{order_details}"""

    for admin in admins:
        admin_id = admin[0]
        send_message(admin_id, message, get_order_management_keyboard(order_id))

# Уведомление админов о вопросе
def notify_admins_about_question(client_id, username, first_name, text):
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM admins')
    admins = cursor.fetchall()
    conn.close()
    
    message = f"""💬 <b>НОВЫЙ ВОПРОС</b>

👤 <b>Клиент:</b> {first_name}
📛 <b>Username:</b> @{username if username else 'нет'}
🆔 <b>ID:</b> <code>{client_id}</code>

❓ <b>Вопрос:</b>
{text}"""

    for admin in admins:
        admin_id = admin[0]
        send_message(admin_id, message, get_chat_management_keyboard(client_id))

# Уведомление админов о сообщении
def notify_admins_about_message(client_id, username, first_name, text):
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM admins')
    admins = cursor.fetchall()
    conn.close()
    
    message = f"""📨 <b>Сообщение от клиента</b>

👤 <b>Клиент:</b> {first_name}
📛 <b>Username:</b> @{username if username else 'нет'}
🆔 <b>ID:</b> <code>{client_id}</code>

💬 <b>Сообщение:</b>
{text}"""

    for admin in admins:
        admin_id = admin[0]
        send_message(admin_id, message, get_chat_management_keyboard(client_id))

# Аналитика консультантов
def show_consultants_analytics(admin_id):
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, nickname, rank, total_orders, successful_orders, rating
        FROM admins 
        WHERE rank IN ('moderator', 'head_moderator', 'owner')
        ORDER BY successful_orders DESC, rating DESC
    ''')
    consultants = cursor.fetchall()
    conn.close()
    
    if not consultants:
        send_message(admin_id, "📊 <b>Нет данных по консультантам</b>")
        return
    
    text = "📈 <b>Аналитика консультантов</b>\n\n"
    
    ranks = {
        "owner": "💎 Владелец",
        "head_moderator": "🔧 Гл. модератор", 
        "moderator": "👨‍💼 Консультант"
    }
    
    for i, consultant in enumerate(consultants, 1):
        user_id, nickname, rank, total_orders, successful_orders, rating = consultant
        
        # Рассчитываем эффективность
        efficiency = (successful_orders / total_orders * 100) if total_orders > 0 else 0
        
        text += f"{i}. {ranks.get(rank, rank)}\n"
        text += f"   👤 <b>{nickname if nickname else 'Без ника'}</b>\n"
        text += f"   📊 <b>Заказы:</b> {successful_orders}/{total_orders}\n"
        text += f"   ⭐ <b>Рейтинг:</b> {rating:.1f}/5.0\n"
        text += f"   📈 <b>Эффективность:</b> {efficiency:.1f}%\n"
        
        # Добавляем эмодзи в зависимости от эффективности
        if efficiency >= 80:
            text += "   🏆 <b>Отлично</b>\n"
        elif efficiency >= 60:
            text += "   👍 <b>Хорошо</b>\n"
        elif efficiency >= 40:
            text += "   ⚠️ <b>Средне</b>\n"
        else:
            text += "   ❌ <b>Низкая</b>\n"
            
        text += "   ————————————\n"
    
    send_message(admin_id, text)

# Управление заказами
def show_order_management(admin_id):
    conn = sqlite3.connect('dripuz.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT o.id, o.user_id, c.first_name, o.status, o.created_date, o.order_details
        FROM orders o
        LEFT JOIN chats c ON o.user_id = c.user_id
        WHERE o.status != 'completed' AND o.status != 'cancelled'
        ORDER BY o.created_date DESC
        LIMIT 10
    ''')
    orders = cursor.fetchall()
    conn.close()
    
    if not orders:
        send_message(admin_id, "📦 <b>Нет активных заказов</b>")
        return
    
    text = "📦 <b>Активные заказы:</b>\n\n"
    
    status_icons = {
        'new': '🆕',
        'in_progress': '🔄', 
        'waiting_payment': '💰',
        'shipped': '🚚',
        'completed': '✅',
        'cancelled': '❌'
    }
    
    status_texts = {
        'new': 'Новый',
        'in_progress': 'В работе',
        'waiting_payment': 'Ожидает оплаты',
        'shipped': 'Отправлен',
        'completed': 'Завершен',
        'cancelled': 'Отменен'
    }
    
    for order in orders:
        order_id, user_id, first_name, status, created_date, order_details = order
        created = datetime.fromisoformat(created_date).strftime("%d.%m %H:%M")
        
        preview = order_details[:50] + "..." if len(order_details) > 50 else order_details
        
        text += f"{status_icons.get(status, '📦')} <b>Заказ #{order_id}</b>\n"
        text += f"👤 <b>Клиент:</b> {first_name}\n"
        text += f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        text += f"📊 <b>Статус:</b> {status_texts.get(status, status)}\n"
        text += f"🕒 <b>Создан:</b> {created}\n"
        text += f"📋 <b>Детали:</b> {preview}\n"
        text += "————————————\n"
    
    send_message(admin_id, text)

# Обработка callback кнопок
def handle_callback_query(callback_data, user_id):
    if callback_data.startswith("close_chat_"):
        client_id = callback_data.replace("close_chat_", "")
        close_chat(user_id, client_id)
    elif callback_data.startswith("reply_chat_"):
        client_id = callback_data.replace("reply_chat_", "")
        send_message(user_id, f"💬 <b>Ответ клиенту {client_id}</b>\n\n<code>/reply {client_id} ваш текст</code>")
    elif callback_data.startswith("order_status_"):
        # Формат: order_status_{order_id}_{new_status}
        parts = callback_data.replace("order_status_", "").split("_")
        if len(parts) >= 2:
            order_id = parts[0]
            new_status = parts[1]
            update_order_status_with_notification(order_id, new_status, user_id)

# Обновление статуса заказа с уведомлением
def update_order_status_with_notification(order_id, new_status, admin_id):
    order_info = update_order_status(order_id, new_status, admin_id)
    
    if order_info:
        client_id, status = order_info
        
        # Уведомляем клиента
        status_messages = {
            'in_progress': "🔄 <b>Ваш заказ принят в работу!</b>\n\nКонсультант обрабатывает ваш заказ.",
            'waiting_payment': "💰 <b>Ожидаем оплату</b>\n\nПосле получения оплаты заказ будет отправлен.",
            'shipped': "🚚 <b>Заказ отправлен!</b>\n\nТрек номер будет отправлен отдельно.",
            'completed': "✅ <b>Заказ завершен!</b>\n\nСпасибо за покупку! Ждем вас снова!",
            'cancelled': "❌ <b>Заказ отменен</b>\n\nПо вопросам обращайтесь к консультанту."
        }
        
        if new_status in status_messages:
            send_message(client_id, status_messages[new_status])
        
        # Уведомляем админа
        send_message(admin_id, f"✅ <b>Статус заказа #{order_id} изменен на: {new_status}</b>")

# Закрытие чата
def close_chat(admin_id, client_id):
    try:
        conn = sqlite3.connect('dripuz.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE chats SET status = "closed" WHERE user_id = ?', (client_id,))
        conn.commit()
        conn.close()
        send_message(client_id, "🔒 <b>Чат закрыт</b>\n\nИспользуйте /start для нового диалога.")
        send_message(admin_id, f"✅ <b>Чат с клиентом {client_id} закрыт</b>")
    except Exception as e:
        send_message(admin_id, f"❌ <b>Ошибка закрытия чата:</b> {e}")

# Обработка команд создателя
def handle_creator_command(user_id, text):
    if text == "/admin" or text == "/start":
        send_message(user_id, "👑 <b>Панель создателя DripUz</b>", get_creator_keyboard())
    elif text == "💬 Активные чаты":
        show_active_chats(user_id)
    elif text == "👥 Админы":
        show_admins_list(user_id)
    elif text == "💳 Карты оплаты":
        show_payment_cards(user_id)
    elif text == "📊 Статистика":
        show_stats(user_id)
    elif text == "📦 Управление заказами":
        show_order_management(user_id)
    elif text == "📈 Аналитика":
        show_consultants_analytics(user_id)
    elif text == "👑 Управление админами":
        show_admin_management(user_id)
    elif text.startswith("/reply"):
        handle_reply_command(user_id, text)
    elif text.startswith("/add_admin"):
        handle_add_admin(user_id, text)
    elif text.startswith("/remove_admin"):
        handle_remove_admin(user_id, text)
    elif text.startswith("/close_chat"):
        parts = text.split(' ')
        if len(parts) == 2:
            close_chat(user_id, parts[1])

# Обработка команд админа
def handle_admin_command(user_id, text):
    if text == "/admin" or text == "/start":
        rank = get_admin_rank(user_id)
        rank_text = {
            "creator": "👑 Создатель",
            "owner": "💎 Владелец",
            "head_moderator": "🔧 Гл. модератор",
            "moderator": "👨‍💼 Консультант"
        }.get(rank, "👨‍💼 Консультант")
        send_message(user_id, f"🔐 <b>Панель {rank_text}</b>", get_admin_keyboard())
    elif text == "💬 Активные чаты":
        show_active_chats(user_id)
    elif text == "👥 Админы":
        show_admins_list(user_id)
    elif text == "💳 Карты оплаты":
        show_payment_cards(user_id)
    elif text == "📊 Статистика":
        show_stats(user_id)
    elif text == "📦 Управление заказами":
        show_order_management(user_id)
    elif text == "📈 Аналитика":
        show_consultants_analytics(user_id)
    elif text.startswith("/reply"):
        handle_reply_command(user_id, text)
    elif text.startswith("/close_chat"):
        parts = text.split(' ')
        if len(parts) == 2:
            close_chat(user_id, parts[1])

# Остальные функции (show_active_chats, show_admins_list, show_payment_cards, show_stats, 
# handle_reply_command, handle_add_admin, handle_remove_admin, show_admin_management) 
# остаются аналогичными предыдущей версии

def main():
    init_db()
    print("🚀 Бот DripUz запущен!")
    print("📱 Канал: @dripuzz")
    print("👑 Создатель ID:", CREATOR_ID)
    print("💬 Ожидаем сообщения...")
    
    last_update_id = None
    
    while True:
        updates = get_updates(last_update_id)
        
        if "result" in updates:
            for update in updates["result"]:
                if "callback_query" in update:
                    callback = update["callback_query"]
                    user_id = callback["from"]["id"]
                    callback_data = callback["data"]
                    handle_callback_query(callback_data, user_id)
                    continue
                    
                if "message" in update:
                    message = update["message"]
                    user_id = message["from"]["id"]
                    username = message["from"].get("username", "")
                    first_name = message["from"].get("first_name", "")
                    text = message.get("text", "")
                    
                    print(f"📥 Получено: {text} от {first_name} ({user_id})")
                    
                    if is_creator(user_id):
                        handle_creator_command(user_id, text)
                    elif is_admin(user_id):
                        handle_admin_command(user_id, text)
                    else:
                        if text == "/start":
                            handle_client_start(user_id, username, first_name)
                        elif text in ["🛍️ Заказать товар", "📦 Наличие товара", "💳 Реквизиты", "💬 Задать вопрос", "❌ Отменить вопрос"]:
                            handle_client_button(user_id, username, first_name, text)
                        else:
                            handle_client_message(user_id, username, first_name, text)
                
                last_update_id = update["update_id"] + 1
        
        time.sleep(1)

if __name__ == '__main__':
    main()