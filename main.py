"""Mood checker."""
import collections
import configparser
import datetime
import json
import os

import vk_api
from vk_api.longpoll import VkEventType, VkLongPoll
from vk_api.utils import get_random_id


class Model:
    """Constructs storage."""

    def __init__(self):
        self.storage = collections.defaultdict(dict)

        self.__load_storage()

    def __load_storage(self):
        if not os.path.isfile("storage.json"):
            self.__save_storage()

        with open("storage.json", "r", encoding="utf-8") as file:
            self.storage = collections.defaultdict(dict, json.load(file))

    def __save_storage(self):
        with open("storage.json", "w", encoding="utf-8") as file:
            json.dump(self.storage, file, ensure_ascii=False)

    def save_mood(self, user, rating: int, description: str):
        curr_date = str(datetime.datetime.now().date())
        self.storage[str(user)][curr_date] = (rating, description)

        self.__save_storage()


class View:
    def __init__(self, vk_session):
        self.vk_session = vk_session
        self.vk = self.vk_session.get_api()

    def __parse_message(self, text):
        words = text.split()
        action = words[0]

        keys = words[1::2]
        values = words[2::2]
        args = dict(zip(keys, values))

        return action, args

    def __parse_event(self, event):
        action, args = self.__parse_message(event.text)
        args["user"] = event.user_id

        return action, args

    def get_actions(self):
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

    def start(self, user):
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
        commands_message = "\n\n".join(command_list)
        message = (
            "Привет! Вот команды, которые можно использовать:\n\n"
            f"{commands_message}"
        )

        with open("keyboard.json", "r", encoding="UTF-8") as keyboard:
            self.show_to_user(user, message, keyboard.read())


class Controller:
    def __init__(self, model, view):
        self.model = model
        self.view = view

    def start(self, user, args):
        self.view.start(user)

    def save_mood(self, user, args):
        with open("keyboard.json", "r", encoding="UTF-8") as file:
            self.view.show_to_user(
            	user,
            	"Введите сегодняшнее настроение",
            	file.read(),
            )
        # get actions from View
        # rating = int()
        rating = 0
        # if rating is None:
        #     raise Exception("Pass 'rating' key in args dict")
        with open("keyboard.json", "r", encoding="UTF-8") as keyboard:
            self.view.show_to_user(user, "Введите описание", keyboard.read())
        description = args.get("descr", "")

        self.model.save_mood(user, rating, description)

        text = (
            f"Ваше настроение сегодня: {rating}\n"
            f"Пара слов о дне: {description}"
        )
        with open("keyboard.json", "r", encoding="UTF-8") as json_file:
            self.view.show_to_user(user, text, json_file.read())

    def get_report(self, user, args):
        ...
        # user_moods = self.model.get_user_moods_for_current_month(user)
        # self.view.send_report_to_user(user, report)

    def set_notification(self, user, args):
        ...
        # self.set_time_to_ask_question(user, new_time)

    def reset_mood(self, user, args):
        ...
        # self.model.reset_today_mood(user)

    def get_info(self, user, args):
        ...
        # self.view.about()

    def handle_error(self, user, args):
        text = "Такой команды нет"
        self.view.show_to_user(user, text)

    def handle_action(self, action, args):
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
