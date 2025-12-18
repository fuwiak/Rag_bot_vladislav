"""
Обработчики для Telegram бота
"""
from aiogram import Dispatcher

from app.bot.handlers.commands import register_commands
from app.bot.handlers.auth_handler import register_auth_handlers
from app.bot.handlers.question_handler import register_question_handlers


def register_handlers(dp: Dispatcher, project_id: str):
    """Регистрация всех обработчиков"""
    register_commands(dp, project_id)
    register_auth_handlers(dp, project_id)
    register_question_handlers(dp, project_id)






