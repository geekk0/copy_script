from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message


async def create_kb(button_labels, callback_data):
    keyboard = []
    row = []
    for label, data in zip(button_labels, callback_data):
        row.append(InlineKeyboardButton(text=label, callback_data=data))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

enhance_rs_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='Запустить', callback_data='Обработка:запустить'),
        InlineKeyboardButton(text='Настройки', callback_data='Обработка:настройки'),
    ]
])