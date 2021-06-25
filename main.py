"""Mood checker."""
import collections
import configparser
import datetime
import json
import os
import statistics
import threading
import time
from enum import Enum

import vk_api
from vk_api.longpoll import VkEventType, VkLongPoll
from vk_api.utils import get_random_id


class State (Enum):
    """States of finite statet machine."""

    MAIN_MENU = 0
    SAVE_MOOD = 1
    SAVE_DESCRIPTION = 2
    SET_NOTIFICATION = 3


STORAGE_FILE_ENCODING = "utf-8"


class Model (object):  # noqa: WPS214
    """Data for work."""

    def __init__(self):
        """Construct storage."""
        self.mood_storage = collections.defaultdict(dict)
        self.ntf_storage = collections.defaultdict(dict)

        self._load_storage()

    def save_mood(self, user, rating: int, description: str):
        """Save mood from user."""
        curr_date = str(datetime.datetime.now().date())
        self.mood_storage[str(user)][curr_date] = (rating, description)

        self._save_mood_storage()

    def save_notifications(self, user, notification_time: str):
        """Save notification time from user."""
        self.ntf_storage[str(user)] = notification_time

        self._save_ntf_storage()

    def refresh_storage(self):
        """Refresh data in file.

        Changed data storage will be written to file.
        """
        self._save_mood_storage()

    def _load_storage(self):
        if not os.path.isfile("notifications.json"):
            self.save_ntf_storage()

        with open(
            "notifications.json",
            "r",
            encoding=STORAGE_FILE_ENCODING,
        ) as ntf_file:
            self.ntf_storage = collections.defaultdict(
                dict,
                json.load(ntf_file),
            )

        if not os.path.isfile("storage.json"):
            self._save_mood_storage()

        with open(
            "storage.json",
            "r",
            encoding=STORAGE_FILE_ENCODING,
        ) as storage_file:
            self.mood_storage = collections.defaultdict(
                dict,
                json.load(storage_file),
            )

    def _save_ntf_storage(self):
        with open(
            "notifications.json",
            "w",
            encoding=STORAGE_FILE_ENCODING,
        ) as ntf_file:
            json.dump(self.ntf_storage, ntf_file, ensure_ascii=False)

    def _save_mood_storage(self):
        with open(
            "storage.json",
            "w",
            encoding=STORAGE_FILE_ENCODING,
        ) as storage_file:
            json.dump(self.mood_storage, storage_file, ensure_ascii=False)


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


def create_report_message(moods):
    """Generate message with stats info."""
    mean_mood = statistics.mean(moods)
    std_mood = round(statistics.pstdev(moods), 2)
    median_mood = statistics.median(moods)
    return (
        f"Ваше среднее настроение за месяц: {mean_mood}\n"
        f"Самое частое настроение за месяц: {median_mood}\n"
        f"Разброс настроений за месяц: {std_mood}"
    )


class Controller (object):  # noqa: WPS214
    """Operates with data."""

    def __init__(self, model, view):
        """Construct operator."""
        self.model = model
        self.view = view
        with open(
            "keyboard.json",
            "r",
            encoding=STORAGE_FILE_ENCODING,
        ) as keyboard:
            self.keyboard = keyboard.read()
        self.ratings = {}
        self.descriptions = {}
        self.notification_times = model.ntf_storage

    def start(self, user):
        """Implement operation "start"."""
        self.view.start(user, self.keyboard)
        self.model.save_notifications(user, "21:00")

    def save_mood(self, user):
        """Implement operation "save"."""
        self.view.show_to_user(
            user,
            "Введите сегодняшнее настроение",
            self.keyboard,
        )
        self.view.curr_state = State.SAVE_MOOD

    def report(self, user):
        """Generate month report about moods."""
        start_date = datetime.date.today().replace(day=1)
        moods = []
        user_notes = self.model.mood_storage.get(str(user))
        while (start_date <= datetime.date.today()):
            note = user_notes.get(str(start_date))
            if note is not None:
                moods.append(note[0])
            start_date += datetime.timedelta(days=1)

        self.view.show_to_user(
            user,
            create_report_message(moods),
            self.keyboard,
        )

    def set_notification(self, user):
        """Implement operation ""notify."""
        self.view.show_to_user(
            user,
            "Введите время уведомлений",
            self.keyboard,
        )
        self.view.curr_state = State.SET_NOTIFICATION

    def reset_mood(self, user):
        """Implement operation "reset"."""
        curr_date = str(datetime.datetime.now().date())
        self.model.mood_storage[str(user)].pop(curr_date, None)
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
            "Отчет": self.report,
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

    def handle_notification_time(self, text, user):
        """Set new time to ask for mood input."""
        self.notification_times[user] = text

        self.model.save_notifications(user, self.notification_times[user])

        message = (
            f"Установлено время уведомления {self.notification_times[user]}"
        )
        self.view.show_to_user(user, message, self.keyboard)
        self.view.curr_state = State.MAIN_MENU

    def schedule_for_sending_ntf(self):
        """Check if it is time to send notification to user."""
        was_ntf_send = False
        while True:
            cur_time = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
            if cur_time.hour == 0 and cur_time.minute == 0:
                was_ntf_send = False
            for user, user_time in self.model.notifications:
                ntf_time = datetime.datetime.strptime(
                    user_time,
                    "%H:%M",
                )
                if (cur_time - ntf_time).seconds <= 60 and not was_ntf_send:
                    self.send_notification(user)
                    was_ntf_send = True
            time.sleep(10)

    def send_notification(self, user):
        """Send notification to user."""
        self.view.show_to_user(
            user,
            "Пора заполнить настроение",
            self.keyboard,
        )


def process_event_from_menu(model, view, controller):
    """Catch event from user and decide what to do next."""
    for event in view.get_actions():
        if view.curr_state == State.MAIN_MENU:
            controller.handle_action(event.text, event.user_id)
        elif view.curr_state == State.SAVE_MOOD:
            controller.handle_mood(event.text, event.user_id)
        elif view.curr_state == State.SAVE_DESCRIPTION:
            controller.handle_description(event.text, event.user_id)
        elif view.curr_state == State.SET_NOTIFICATION:
            controller.handle_notification_time(event.text, event.user_id)


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("config.ini")

    token = config["vk"]["token"]

    vk_session = vk_api.VkApi(token=token)

    model = Model()
    view = View(vk_session)
    controller = Controller(model, view)

    thread_for_events = threading.Thread(
        target=process_event_from_menu,
        args=(model, view, controller),
    )
    thread_for_events.start()

    thread_for_notify = threading.Thread(
        target=controller.schedule_for_sending_ntf,
    )
    thread_for_notify.start()
