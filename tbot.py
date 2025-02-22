from  dotenv import load_dotenv
import os
from types import SimpleNamespace
import telebot
from telebot import types
import threading
import uuid
import os
import csv

from order_manager import FoodOrderManager, init_fo_manager
from db_module import DBConnector, DBManager
from session import UsersSession

from design import (show_main_menu,
                    show_menu_categories,
                    show_menu_category_items,
                    select_quantity,
                    show_help,
                    show_feedback,
                    online_pay,
                    show_pay_form,)
from design import (make_menu_categories,
                    make_menu_category_items,
                    make_quantity_dialog,
                    menu_tree_previous,
                    create_keyboard_variable_rows
                    )
#from payment import process_payment_animation

# Инициализация бота и загрузка переменных окружения из .venv/.env
env_path = os.path.join(os.path.dirname(__file__), ".venv", ".env")
load_dotenv(env_path)
TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)
commands = [
    types.BotCommand("start", "Запустить бота"),
    types.BotCommand("help", "Помощь по командам"),
    ]
bot.set_my_commands(commands)


# Глобальная переменная для максимального количества порций
number_of_seats = 8  # Максимальное количество порций


user_data = UsersSession()

def delete_old_message(message):
    user_id = message.from_user.id
    if user_data[user_id]["old_message"] is not None:
        try:
            bot.delete_message(message.chat.id, user_data[user_id]["old_message"][1])
        except telebot.apihelper.ApiTelegramException as e:
            print("Ошибка при удалении сообщения",e)
        user_data[message.from_user.id]["old_message"] = None


# Инициирование события /start программно
def trigger_start(chat_id):
    # Создаем фейковое сообщение
    class FakeMessage:
        def __init__(self, message):
            self.chat = SimpleNamespace(id=message.chat.id)
            self.text = '/start'
            self.from_user = types.User(id= message.chat.id,
                                        is_bot=False,
                                        first_name=message.chat.first_name,
                                        last_name=message.chat.last_name,
                                        username=message.chat.username
                                        )

    # Вызываем обработчик как будто это сообщение от пользователя
    start(FakeMessage(chat_id))

# Команда старта
@bot.message_handler(commands=['start'])
def start(message):
    if hasattr(message, 'message_id'):
        delete_old_message(message)
        bot.delete_message(message.chat.id, message.message_id)
    food_order_manager = init_fo_manager()
    user_id = message.from_user.id
    # user_data[user_id] = user_data.get(user_id, {})
    if user_data[user_id]["order_id"] is None:
        order_pending = food_order_manager.get_user_orders_by_status(user_id)
        if order_pending and len(order_pending) > 0:
            order_pending = order_pending[-1]
            user_data[user_id]['order_id'] = order_pending[0]

    #user_data[user_id]["old_message"] = message


    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    full_name = f"{first_name or ''} {last_name or ''}"
    if full_name == " ":
        full_name = username
    # Проверка, существует ли пользователь
    if not food_order_manager.check_user_exists(telegram_id=user_id):
        if food_order_manager.create_user(user_id, username, first_name, last_name):
            bot.send_message(message.chat.id, f"😀 {full_name}, Вы успешно зарегистрированы!👍")
    else:
        bot.send_message(message.chat.id, f"👏С возвращением, {full_name} !🤗")

    # Отправка главного меню
    user_data[user_id]["old_message"] = show_main_menu(bot,message,user_data)
    food_order_manager.db_manager.close()
    print(user_data)

@bot.message_handler(commands=['help'])
def help(message):
    delete_old_message(message)
    show_help(bot, message, user_data)

@bot.message_handler(func=lambda message: message.text == 'Отзывы')
def feedback(message):
    delete_old_message(message)
    show_feedback(bot, message, user_data)
# https://github.com/swiftins/MY-BISTRO/blob/OOP-version/webapp/
# def webapp_feedback(message):
#     try:
#         data = json.loads(message.web_app_data.data)
#         review = data.get("review", "Ошибка при получении отзыва")
#         bot.send_message(message.chat.id, f"Спасибо за ваш отзыв: {review}")
#     except Exception as e:
#         bot.send_message(message.chat.id, "Произошла ошибка при обработке отзыва.")
#

# Показать меню
@bot.message_handler(func=lambda message: message.text == 'Меню')
def show_menu(message):
    delete_old_message(message)
    user_id = message.from_user.id
    #user_data[user_id] = user_data.get(user_id, {})
    if not user_data[user_id]:
        trigger_start(message)
        return
    #delete_old_message(message)
    user_data[user_id]["old_message"] = make_menu_categories(bot,message,user_data)

    bot.delete_message(message.chat.id, message.message_id)
    print(user_data[user_id])

@bot.message_handler(func=lambda message: message.text == 'Выйти')
def close_menu(message):
    delete_old_message(message)
    bot.delete_message(message.chat.id, message.message_id)
    msg =bot.send_message(message.chat.id, " ", reply_markup=types.ReplyKeyboardRemove())  # Пустое сообщение
    bot.delete_message(message.chat.id, msg.message_id)


# Показать блюда в категории
@bot.message_handler(func=lambda message: message.text in [category[1] for category in init_fo_manager().get_menu_categories()])
def show_category_items(message):
    delete_old_message(message)
    user_id = message.from_user.id
    # user_data[user_id] = user_data.get(user_id, {})
    if not user_data[user_id]:
        trigger_start(message)
        return False
    user_data[user_id]["old_message"] == make_menu_category_items(bot, message, user_data)
    print(user_data[user_id])


# Обработчик выбора блюда
@bot.message_handler(func=lambda message: message.text.endswith('руб.'))
def select_item_quantity(message):
    delete_old_message(message)
    user_id = message.from_user.id
    # user_data[user_id] = user_data.get(user_id, {})
    if not user_data[user_id]:
        trigger_start(message)
        return False
    make_quantity_dialog(bot, message, user_data)

# Обработчик ввода количества
#@bot.message_handler(func=lambda message: message.text.endswith('шт.'))
@bot.message_handler(func=lambda message: message.text.isdigit() and 1<=int(message.text) <= number_of_seats)
def add_item_to_order(message):
    #delete_old_message(message)
    user_id = message.from_user.id
    quantity = int(message.text)
    print (user_data)
    user_data[user_id] = user_data.get(user_id, {})
    if not user_data[user_id]['selected_item']:
        bot.send_message(message.chat.id, "Ошибка: блюдо не выбрано.")
        return

    food_order_manager = init_fo_manager()
    item_name = user_data[user_id]['selected_item']
    item = next(item for item in food_order_manager.get_menu_items() if item[2] == item_name)

    # Создание заказа, если его еще нет
    if  not user_data[user_id]['order_id']:
        result =food_order_manager.create_order(user_id, total_price=0)
        if result[0]:
            user_data[user_id]['order_id'] = result[1]
        else:
            bot.send_message(message.chat.id, f"Ошибка при создании заказа.{result[1]}")
            return
    # Добавление блюда в заказ
    food_order_manager.add_item_to_order(user_data[user_id]['order_id'], item[0], quantity)
    bot.send_message(message.chat.id, f"{quantity} порций '{item_name}' добавлено в заказ!")

    # Очищаем выбранное блюдо
    del user_data[user_id]['selected_item']

    # Возвращаем пользователя к выбору категорий и добавляем кнопку "Оформить заказ"
    show_menu_with_checkout(message.chat.id)
    food_order_manager.db_manager.close()

# Показать меню с кнопкой "Оформить заказ"
def show_menu_with_checkout(chat_id):
    food_order_manager = init_fo_manager()
    categories = food_order_manager.get_menu_categories()
    markup = types.ReplyKeyboardMarkup(row_width=2)
    for category in categories:
        markup.add(types.KeyboardButton(category[1]))
    markup.add(types.KeyboardButton('Оформить заказ'))
    markup.add(types.KeyboardButton('Назад'))
    bot.send_message(chat_id, "Выберите категорию или оформите заказ:", reply_markup=markup)
    food_order_manager.db_manager.close()


# Обработчик оформления заказа
@bot.message_handler(func=lambda message: message.text == 'Оформить заказ')
def checkout_order(message):
    chat_id = message.chat.id
    bot.delete_message(chat_id, message.message_id)
    user_id = message.from_user.id
    print(f"{user_id} - Нажал 'Оформить заказ'")
    food_order_manager = init_fo_manager()
    #user_data[user_id] = user_data.get(user_id, {})
    msg = None
    order_id=None
    if  user_data[user_id]['order_id'] :
        order_id = user_data[user_id]['order_id']
        status=food_order_manager.get_order_status(order_id)
        if status:
            status = status[0][0][0]
            if status != "pending":
                del(user_data[user_id]['order_id'])
                order_id=None
    if not order_id:
        order_pending = food_order_manager.get_user_orders_by_status(user_id)

        if order_pending and len(order_pending) > 0:
            user_data[user_id]['order_id'] = order_pending[-1][0]
            msg = bot.send_message(chat_id, "Найден заказ.")
        elif not order_pending:
            msg = bot.send_message(chat_id, "Нет активных заказов.")
            return
        else:
            msg.bot.send_message(chat_id, "Ваш заказ пуст.")
            return



    # Получаем информацию о заказе
    order_items = food_order_manager.get_order_items(order_id)
    if len(order_items) == 0:
        bot.send_message(chat_id, "Ваш заказ пуст.")
        return
    total_price = sum(item[2] * item[3] for item in order_items)  # price * quantity
    title = f"<b>Ваш заказ</b> :  {total_price} руб."
    # Формируем инлайн-клавиатуру с заказом
    kbd = create_keyboard_variable_rows(order_items)
    user_data[user_id]["order_form"] = bot.send_message(chat_id, title, reply_markup=kbd, parse_mode='HTML')
    # Возвращаем пользователя в главное меню
    show_main_menu(bot,message,user_data)
    food_order_manager.db_manager.close()
    if msg:
        bot.delete_message(message.chat.id, msg.message_id)


@bot.message_handler(func=lambda message: message.text == "Почистить чат")
def clear_chat(message):
    chat_id = message.chat.id

    # Получаем последние 10 сообщений в чате
    message_ids = [message.message_id - i for i in range(100)]

    # Пытаемся удалить каждое сообщение
    for msg_id in message_ids:
        try:
            bot.delete_message(chat_id, msg_id)
        except Exception as e:
            pass
            #print(f"Не удалось удалить сообщение с ID {msg_id}: {e}")

@bot.message_handler(func=lambda message: message.text == 'X' or message.text == 'Назад' or message.text == '0' or message.text == '❌')
def go_back(message):
    delete_old_message(message)
    user_id = message.from_user.id
    if user_data[user_id] is None or user_data[user_id]["step"] is None:
        show_main_menu(bot, message, user_data)
        bot.delete_message(message.chat.id, message.message_id)
        return

    #previous_step = menu_tree_previous[usr_data["step"]][0]
    previous_menu = menu_tree_previous[user_data[user_id]["step"]][1]
    previous_menu(bot, message, user_data)
    bot.delete_message(message.chat.id, message.message_id)

# Показать заказы пользователя
@bot.message_handler(func=lambda message: message.text == 'Мои заказы')
def show_user_orders(message):
    food_order_manager = init_fo_manager()
    user_id = message.from_user.id
    print(f"{user_id} - Нажал 'Мои заказы'")
    bot.delete_message(message.chat.id, message.message_id)
    food_order_manager.update_all_orders()
    orders = food_order_manager.get_order_by_id_or_user_id(user_id=user_id)
    #orders = food_order_manager.get_user_orders(user_id)
    if orders:
        bot.send_message(message.chat.id,f"<b>{"*"*20} Заказы {"*"*20}</b>", parse_mode="HTML")
        for order in orders:
            if order[6] == "pending":
                end = "Оформляется"
            elif order[6] == "paid":
                end = "Оплачен "+order[5]
            elif order[6] == "cash_pending":
                end ="В работе, оплата наличными"
            else:
                end = "Статус неопределен"
            bot.send_message(message.chat.id, f"#{order[1]}#|{order[3]} | {order[4]} : {order[2]} руб.\n>{end}",)
        bot.send_message(message.chat.id, f"<b>{"*" * 50}</b>", parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "У вас пока нет заказов.")
    food_order_manager.db_manager.close()

# Специальная команда для админа
@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.text == '/admin_secret_command':
        bot.send_message(message.chat.id, "Пожалуйста, загрузите CSV файл.")
        bot.register_next_step_handler(message, handle_csv)

# Обработка CSV файла
def handle_csv(message):
    if message.document:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open("uploaded_file.csv", "wb") as f:
            f.write(downloaded_file)
        bot.send_message(message.chat.id, "CSV файл успешно загружен.")
    else:
        bot.send_message(message.chat.id, "Пожалуйста, загрузите CSV файл.")

@bot.message_handler(func=lambda message: True)
def handle_unprocessed_messages(message):
    print(f"Необработанное сообщение от {message.from_user.username or message.from_user.first_name}: {message.text}")

# Обработка оплаты
@bot.callback_query_handler(func=lambda call: call.data == ('Оплатить'))
def handle_pay_callback(call):
    user_id = call.from_user.id
    if user_data[user_id]["order_id"] and isinstance(user_data[user_id]["order_form"],types.Message) :
        food_order_manager = init_fo_manager()
        order_id = user_data[user_id]["order_id"]
        order = food_order_manager.get_order_by_id_or_user_id(user_id=user_id,order_id=order_id)
        if not order:
            print("Error in query.")
            return
        order=order[0]
        if order[-1] == "pending":
            user_data[user_id]["pay_order"] = order
            bot.delete_message(call.message.chat.id, call.message.message_id)
            user_data[user_id]["old_message"] = show_pay_form(bot,call.message,user_data)
            #online_pay(bot,call.message,user_data)
            # threading.Thread(
            #     target=process_payment_animation,
            #     args=(bot,
            #           call.message,
            #           order[1],
            #           order[3],
            #           order[2],
            #           order_id
            #           )
            # ).start()

    else:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Сессия была прервана. Используйте нижнее меню")
        trigger_start(call.message)
        return




@bot.callback_query_handler(func=lambda call: call.data == ('Назад'))
def handle_back_callback(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)



# Удаление блюда из заказа
@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def handle_delete_callback(call):
    # Извлекаем данные после 'delete_'
    user_id = call.from_user.id
    if user_data[user_id]["order_form"]:
        item_to_delete = call.data[len('delete_'):]
    else:
        bot.send_message(call.message.chat.id, "Сессия была прервана. Используйте нижнее меню")
        trigger_start(call.message)
        return


    # Выполняем удаление
    food_order_manager = init_fo_manager()
    food_order_manager.delete_order_item(item_to_delete)
    food_order_manager.update_all_orders()
    order_items = food_order_manager.get_order_items(user_data[call.from_user.id]["order_id"])
    if len(order_items) == 0:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Ваш заказ пуст.")
        return
    total_price = sum(item[2] * item[3] for item in order_items)  # price * quantity
    title = f"<b>Ваш заказ</b> :  {total_price} руб."
    bot.edit_message_text(chat_id=call.message.chat.id,
                                  message_id=call.message.message_id,
                                  text=title,
                                  reply_markup=create_keyboard_variable_rows(order_items),
                                  parse_mode='HTML')
    bot.send_message(call.message.chat.id, "Пункт заказа удален.")


# Добавление блюда в заказ
@bot.callback_query_handler(func=lambda call: call.data.isdigit())
def handle_callback_query(call):
    print(f"Callback query from {call.from_user.username or call.from_user.first_name}: {call.data}")
    user_id = call.from_user.id
    quantity = int(call.data)
    if quantity <= 0:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return
    print(user_data)

    if not user_data[user_id]['selected_item']:
        bot.send_message(call.message.chat.id, "Сессия была прервана. Используйте нижнее меню")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        trigger_start(call.message)
        return

    if user_data[user_id]["step"] != "Item_quantity":
        bot.send_message(call.message.chat.id, "Сессия была прервана. Используйте нижнее меню")
        return

    if not user_data[user_id]["selected_item"]:
        bot.send_message(call.message.chat.id, "Ошибка: блюдо не выбрано.")
        return

    food_order_manager = init_fo_manager()
    item_name = user_data[user_id]['selected_item']
    item = food_order_manager.get_menu_item_id_by_name(item_name)[0]
    bot.delete_message(call.message.chat.id, call.message.message_id)

    #item = next(item for item in food_order_manager.get_menu_items() if item[2] == item_name)


    # Создание заказа, если его еще нет
    if  not user_data[user_id]['order_id']:
        order_pending = food_order_manager.get_user_orders_by_status(user_id)
        if order_pending and len(order_pending) > 0:
            user_data[user_id]['order_id'] = order_pending[-1][0]
            bot.send_message(call.message.chat.id, "Найден незавершенный заказ. Продолжаю заполнение")
        else:
            result = food_order_manager.create_order(user_id, total_price=0)
            if result[0]:
                order_id = result[1]
                user_data[user_id]['order_id'] = result[1]
            else:
                bot.send_message(call.message.chat.id, f"Ошибка при создании заказа {result[1]}" )
                return

    # Добавление блюда в заказ
    result = food_order_manager.add_item_to_order(user_data[user_id]['order_id'], item[0], quantity)
    if result:
        text = f"{quantity} порций '{item_name}' добавлено в заказ!"
    else:
        text = f"Ошибка при добавлении порций '{item_name}' в заказ!"
    bot.send_message(call.message.chat.id, text)
    food_order_manager.update_all_orders()

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_'))
def handle_callback_query_pay(call):
    user_id = call.from_user.id
    method = call.data[len('pay_'):]
    bot.delete_message(call.message.chat.id, call.message.message_id)
    if not user_data[user_id]['order_id'] or not user_data[user_id]["pay_order"]:
        bot.send_message(call.message.chat.id, "Сессия была прервана. Используйте нижнее меню")
        return

    if method != "cache":
        online_pay(bot,call.message,user_data)
        return
    order = user_data[user_id]["pay_order"]
    final_message = (f"💰 Отличный выбор! Оплата наличными – это классика! 💵\n"
                     f"*Ваш заказ #*[ {order[1]} ]\n"
                     f"*{order[3]}!* Пожалуйста, приготовьте сумму: *{order[2]:,.2f}руб.* к оплате.\n"
                     f" Вы сможете произвести оплату при получении. 🚀🍽️\n"
                     f"Если у вас есть вопросы – мы всегда на связи! 📞😊\n")
    bot.send_message(call.message.chat.id, final_message, parse_mode = "Markdown")
    food_order_manager = init_fo_manager()
    result = food_order_manager.update_order_status(user_data[user_id]["order_id"], "cash_pending")
    food_order_manager.db_manager.close()



    print(f"Callback query from {call.from_user.username or call.from_user.first_name}: {call.data}")



@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query_unknown(call):
    print(f"Callback query from {call.from_user.username or call.from_user.first_name}: {call.data}")


# Запуск бота
bot.polling(none_stop=True)
