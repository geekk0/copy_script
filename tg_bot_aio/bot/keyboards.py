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

modes_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='Индексация', callback_data='Индексация'),
        InlineKeyboardButton(text='Обработка', callback_data='Обработка'),
        InlineKeyboardButton(text='ИИ Обработка', callback_data='ИИ Обработка')
    ],
    [
        InlineKeyboardButton(text='Ссылка на видео', callback_data='Ссылка на видео'),
        InlineKeyboardButton(text='Очереди ФШ', callback_data='Очереди ФШ'),
        InlineKeyboardButton(text='Статистика', callback_data='Статистика'),
    ]

])

enhance_rs_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='Запустить', callback_data='Обработка:запустить'),
        InlineKeyboardButton(text='Настройки', callback_data='Обработка:настройки'),
    ]
])