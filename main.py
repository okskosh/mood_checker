"""Mood checker."""
import collections
import configparser
import datetime
import json
import os

import vk_api
from vk_api.longpoll import VkEventType, VkLongPoll
from vk_api.utils import get_random_id


class Model (object):
    """Data for work."""

    def __init__(self):
        """Construct storage."""
        self.storage = collections.defaultdict(dict)

        self.__load_storage()

    def save_mood(self, user, rating: int, description: str):
        """Save mood from user."""
        curr_date = str(datetime.datetime.now().date())
        self.storage[str(user)][curr_date] = (rating, description)

        self.__save_storage()

    def _load_storage(self):
        if not os.path.isfile("storage.json"):
            self.__save_storage()

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

    def get_actions(self):
        """Catches events that user produce.

        Yields:
            tuple: parameters of every event.
        """
        longpoll = VkLongPoll(self.vk_session)
        for event in longpoll.listen():
            is_message = (event.type == VkEventType.MESSAGE_NEW)
            if is_message and event.to_me and event.text:
                action, args = self.__parse_event(event)

                yield (action, args)

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
        message = (
            "Привет! Вот команды, которые можно использовать:\n\n"
            "\n\n".join(command_list)
        )

        self.show_to_user(user, message, keyboard)

    def _parse_message(self, text):
        words = text.split()
        action = words[0]

        keys = words[1::2]
        descriptions = words[2::2]
        args = dict(zip(keys, descriptions))

        return action, args

    def _parse_event(self, event):
        action, args = self.__parse_message(event.text)
        args["user"] = event.user_id

        return action, args


class Controller (object):
    """Operates with data."""

    def __init__(self, model, view):
        """Construct operator."""
        self.model = model
        self.view = view
        with open("keyboard.json", "r", encoding="UTF-8") as keyboard:
            self.keyboard = keyboard.read()

    def start(self, user, args):
        """Implement operation "start"."""
        self.view.start(user, self.keyboard)

    def save_mood(self, user, args):
        """Implement operation "save"."""
        self.view.show_to_user(
            user,
            "Введите сегодняшнее настроение",
            self.keyboard,
        )

        rating = 0
        self.view.show_to_user(user, "Введите описание", self.keyboard)
        description = args.get("descr", "")

        self.model.save_mood(user, rating, description)

        text = (
            f"Ваше настроение сегодня: {rating}\n"
            f"Пара слов о дне: {description}"
        )
        self.view.show_to_user(user, text, self.keyboard)

    def handle_error(self, user, args):
        """Catch wrong operation."""
        text = "Такой команды нет"
        self.view.show_to_user(user, text, self.keyboard)

    def handle_action(self, action, args):
        """Catch action."""
        user = args.get("user", "unknown_user")

        action_handler = {
            "Начать": self.start,
            "Сохранить": self.save_mood,
            "Отчет": self.get_report,
            "Уведомления": self.set_notification,
            "Сбросить": self.reset_mood,
            "Информация": self.get_info,
        }

        action_handler.get(action, self.handle_error)(user, args)


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("config.ini")

    token = config["vk"]["token"]

    vk_session = vk_api.VkApi(token=token)

    model = Model()
    view = View(vk_session)
    controller = Controller(model, view)

    for action, args in view.get_actions():
        controller.handle_action(action, args)
