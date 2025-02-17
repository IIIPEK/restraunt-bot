import telebot
from telebot import types
import os
from order_manager import FoodOrderManager
from db_module import DBConnector, DBManager
import uuid
from order_manager import FoodOrderManager, init_fo_manager
from design import create_reply_kbd, create_inline_kbd

# Показать главное меню
def show_main_menu(bot,message,user_data):

    main_menu = ["Меню","Мои заказы", "Отзывы", "Выйти"]
    keyboard = create_reply_kbd(row_width=2, values=main_menu, back = None)
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=keyboard)
    print(user_data)
    user_data[message.from_user.id].update({"step" : "Main_menu"})
    pass

def show_menu_categories(bot,message,categories,user_data):
    category = [row[1] for row in categories]
    keyboard = create_reply_kbd(row_width=3, values=category, back="Назад")
    bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=keyboard)
    user_data[message.from_user.id].update( {"step" : "Category_menu"})
    pass

def show_menu_category_items(bot,message,items,user_data):
    item = [f"{row[2]} - {row[4]} руб." for row in items]
    keyboard = create_reply_kbd(row_width=3, values=item, back="Назад")
    bot.send_message(message.chat.id, "Выберите блюдо:", reply_markup=keyboard)
    user_data[message.from_user.id].update( {"step": "Item_menu", "category": items[0][1]})
    pass

def select_quantity(bot,message,item_name,image_path=None,number_of_seats = 8):
    keyboard = create_inline_kbd(row_width=4,nums=number_of_seats)
    if image_path is not None:
        with open(image_path, 'rb') as photo:
            bot.send_photo(message.chat.id,
                           photo=photo,
                           caption=f"{item_name} ",
                           reply_markup=keyboard)


    #bot.send_message(message.chat.id, "Выберите количество:", reply_markup=keyboard)


def make_menu_categories(bot,message,user_data):
    food_order_manager = init_fo_manager()
    categories = food_order_manager.get_menu_categories()
    show_menu_categories(bot,message,categories,user_data)
    food_order_manager.db_manager.close()

def make_menu_category_items(bot,message,user_data):
    food_order_manager = init_fo_manager()
    category_name = message.text
    category_id = next(
        category[0] for category in food_order_manager.get_menu_categories() if category[1] == category_name)
    items = food_order_manager.get_menu_items(category_id=category_id)
    show_menu_category_items(bot, message, items, user_data)
    food_order_manager.db_manager.close()

def make_quantity_dialog(bot,message,user_data):
    food_order_manager = init_fo_manager()
    user_id = message.from_user.id
    item_name = message.text.split(' - ')[0]
    item_ifo = food_order_manager.get_menu_item_id_by_name(item_name)
    item_id=item_ifo[0]
    item_category = food_order_manager.get_menu_categories(item_id[1])[0][1]
    user_data[user_id]['selected_item'] = item_name
    user_data[user_id]["step"] = "Item_quantity"
    user_data[user_id]["item_id"]= item_id
    user_data[user_id]["category"] = item_category[2:-1]
    folder=(user_data[user_id]["category"].split(" ")[0]).lower()
    file="_".join(user_data[user_id]["selected_item"].split(" "))+".jpg"
    print(user_data)
    image_path = os.path.join('img', folder, file)
    print(user_data)
    select_quantity(bot, message, item_name, image_path=image_path)