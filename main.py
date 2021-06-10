"""Mood checker."""
import collections
import configparser
import datetime
import json
import os
from enum import Enum

import vk_api
from vk_api.longpoll import VkEventType, VkLongPoll
from vk_api.utils import get_random_id


class State (Enum):
    """States of finite statet machine."""

    MAIN_MENU = 0
    SAVE_MOOD = 1
    SAVE_DESCRIPTION = 2


class Model (object):
    """Data for work."""

    def __init__(self):
        """Construct storage."""
        self.storage = collections.defaultdict(dict)

        self._load_storage()

    def save_mood(self, user, rating: int, description: str):
        """Save mood from user."""
        curr_date = str(datetime.datetime.now().date())
        self.storage[str(user)][curr_date] = (rating, description)

        self._save_storage()

    def refresh_storage(self):
        """Refresh data in file.

        Changed data storage will be written to file.
        """
        self._save_storage()

    def _load_storage(self):
        if not os.path.isfile("storage.json"):
            self._save_storage()

        with open("storage.json", "r", encoding="utf-8") as storage_file:
            self.storage = collections.defaultdict(
                dict,
                json.load(storage_file),
            )

    def _save_storage(self):
        with open("storage.json", "w", encoding="utf-8") as storage_file:
            json.dump(self.storage, storage_file, ensure_ascii=False)


class View (object):
    """Interface for communication with user."""

    def __init__(self, vk_session):
        """Construct session."""
        self.vk_session = vk_session
        self.vk = self.vk_session.get_api()
        self.curr_state = State.MAIN_MENU

    def get_actions(self):
        """Catches events that user produce.

        Yields:
            event from vk longpoll.
        """
        longpoll = VkLongPoll(self.vk_session)
        for event in longpoll.listen():
            is_message = (event.type == VkEventType.MESSAGE_NEW)
            if is_message and event.to_me and event.text:
                yield event

    def show_to_user(self, user, text, keyboard):
        """Send message with specified text to user."""
        self.vk.messages.send(
            user_id=user,
            message=text,
            random_id=get_random_id(),
            keyboard=keyboard,
        )

    def start(self, user, keyboard):
        """Send start message with info to user."""
        options = collections.OrderedDict({
            "Сохранить": "сохраняет сегодняшнее настроение",
            "Отчет": "составляет отчёт о настроении за последний месяц",
            "Уведомления": "устанавливает время для отправки напоминания",
            "Сбросить": "сбрасывает сегодняшнее настроение",
            "Информация": "информация о приложении",
        })

        command_list = []
        for (key, option) in options.items():
            command_list.append((f"{key} - {option}"))
        options_message = "\n\n".join(command_list)

        self.show_to_user(
            user,
            "Привет! Вот команды, которые можно использовать:\n\n"
            f"{options_message}",
            keyboard,
        )


class Controller (object):  # noqa: WPS214
    """Operates with data."""

    def __init__(self, model, view):
        """Construct operator."""
        self.model = model
        self.view = view
        with open("keyboard.json", "r", encoding="UTF-8") as keyboard:
            self.keyboard = keyboard.read()
        self.ratings = {}
        self.descriptions = {}

    def start(self, user):
        """Implement operation "start"."""
        self.view.start(user, self.keyboard)

    def save_mood(self, user):
        """Implement operation "save"."""
        self.view.show_to_user(
            user,
            "Введите сегодняшнее настроение",
            self.keyboard,
        )
        self.view.curr_state = State.SAVE_MOOD

    def get_report(self, user):
        """Implement operation "report"."""
        return 0

    def set_notification(self, user):
        """Implement operation ""notify."""
        return 0

    def reset_mood(self, user):
        """Implement operation "reset"."""
        curr_date = str(datetime.datetime.now().date())
        self.model.storage[str(user)].pop(curr_date, None)
        self.view.show_to_user(
            user,
            "Запись о сегодняшнем настроении сброшена.",
            self.keyboard,
        )

        self.model.refresh_storage()

    def show_info(self, user):
        """Implement operation "info"."""
        message = "Mood Checker - это чатбот Вконтакте, который позволяет отслеживать настоение каждый день.\n"  # noqa: E501
        self.view.show_to_user(
            user,
            message,
            self.keyboard,
        )

    def handle_error(self, user):
        """Catch wrong operation."""
        text = "Такой команды нет"
        self.view.show_to_user(user, text, self.keyboard)

    def handle_action(self, action, user):
        """Catch action."""
        action_handler = {
            "Начать": self.start,
            "Сохранить": self.save_mood,
            "Отчет": self.get_report,
            "Уведомления": self.set_notification,
            "Сбросить": self.reset_mood,
            "Информация": self.show_info,
        }

        action_handler.get(action, self.handle_error)(user)

    def handle_mood(self, text, user):
        """Catch mood."""
        try:
            self.ratings[user] = int(text)
        except ValueError:
            self.view.show_to_user(user, "Попробуйте снова", self.keyboard)
            return

        self.view.show_to_user(user, "Введите описание", self.keyboard)
        self.view.curr_state = State.SAVE_DESCRIPTION

    def handle_description(self, text, user):
        """Catch description."""
        self.descriptions[user] = text

        self.model.save_mood(user, self.ratings[user], self.descriptions[user])

        message = (
            f"Ваше настроение сегодня: {self.ratings[user]}\n"
            f"Пара слов о дне: {self.descriptions[user]}"
        )
        self.view.show_to_user(user, message, self.keyboard)
        self.view.curr_state = State.MAIN_MENU


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("config.ini")

    token = config["vk"]["token"]

    vk_session = vk_api.VkApi(token=token)

    model = Model()
    view = View(vk_session)
    controller = Controller(model, view)

    for event in view.get_actions():
        if view.curr_state == State(0):
            action = event.text
            user = event.user_id
            controller.handle_action(action, user)
        elif view.curr_state == State(1):
            controller.handle_mood(event.text, event.user_id)
        elif view.curr_state == State(2):
            controller.handle_description(event.text, event.user_id)
