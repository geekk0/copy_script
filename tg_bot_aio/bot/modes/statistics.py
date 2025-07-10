import os
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ChatPhoto
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from ..bot_setup import form_router, logger
from ..keyboards import create_kb
from ..middleware import ChatIDChecker
from ..service import studio_names, mode_names
from ..utils import (run_indexing, check_ready_for_index,
                     change_ownership, change_folder_permissions,
                     add_to_ai_queue, run_rs_enhance)


class StatisticsForm(StatesGroup):
    get_stats = State()


async def start_stats_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data
    logger.info(f'mode: {mode}')
    await state.set_state(StatisticsForm.get_stats)
    await get_stats(callback, state)


async def get_stats(callback: CallbackQuery, state: FSMContext):
    host = "http://127.0.0.1:6677"
    url = f"{host}/statistics/tasks"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    tasks_stats = response.json()
    summary_tasks_stats = tasks_stats['status_summary']
    summary_tasks_stats_text = '\n'.join([f"{k}: {v}" for k, v in summary_tasks_stats.items()])

    recent_tasks: list = tasks_stats['latest_tasks']
    recent_tasks_text = format_tasks_for_telegram(recent_tasks)

    async with httpx.AsyncClient() as client:
        response = await client.get(url=f"{host}/statistics/clients")

    clients_stats = response.json()
    summary_clients_stats = clients_stats['total_clients']
    recent_clients = clients_stats['latest_clients']
    recent_clients_text = format_clients_for_telegram(recent_clients)

    await callback.message.edit_text(text=f"Задачи (по статусам):\n{summary_tasks_stats_text} \n\n"
                                          f"Последние: \n{recent_tasks_text} \n\n\n"
                                          f"Клиентов всего: {summary_clients_stats}\f\n\n"
                                          f"Последние: \n{recent_clients_text}\f")


def format_tasks_for_telegram(tasks: list) -> str:
    lines = []
    for task in tasks:
        created_at = datetime.fromisoformat(task['created_at']) #.astimezone(ZoneInfo('Europe/Moscow'))
        dt_str = created_at.strftime('%d.%m %H:%M')
        client = task['client']
        line = (
            f"ID#{task['id']} | Создана: {dt_str} |"
            f"{task['status']} | "
            # f"📁 {task['folder_path']} | "
            f"📞 {client['phone_number']} | "
            f"📄 {len(task['files_list'])} фaйла."
        )
        lines.append(line)

    return "\n".join(lines)


def format_clients_for_telegram(data: list) -> str:
    clients = data
    if not clients:
        return "Клиенты не найдены."

    def format_phone(phone: str) -> str:
        return f"+7{phone[1:]}" if phone else "—"

    lines = []
    for client in clients:
        line = (
            f"👤 ID#{client['id']} | "
            f"📞 {format_phone(client.get('phone_number'))} | "
            f"🧾 YClients: {client['yclients_id']} | "
            f"💬 Chat ID: {client['chat_id']}"
        )
        lines.append(line)

    return "\n".join(lines)

