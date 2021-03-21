import collections
import datetime
import json
import os
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType


class Model:
    def __load_storage(self):
        if not os.path.isfile("storage.json"):
            self.__save_storage()

        with open("storage.json", "r", encoding="utf-8") as file:
            self.storage = collections.defaultdict(dict, json.load(file))

    def __save_storage(self):
        with open("storage.json", "w", encoding="utf-8") as file:
            json.dump(self.storage, file, ensure_ascii=False)

    def __init__(self):
        self.storage = collections.defaultdict(dict)

        self.__load_storage()

    def save_mood(self, user, rating: int, description: str):
        self.storage[str(user)][str(datetime.datetime.now().date())] = (rating, description)

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

    def get_actions(self):
        longpoll = VkLongPoll(self.vk_session)
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text:
                action, args = self.__parse_message(event.text)
                args["user"] = event.user_id

                yield (action, args)

    def send_message(self, user, text):
    	self.vk.messages.send(user_id=user, message=text, random_id=self.get_random_id())

    def get_random_id(self):
    	return int(datetime.datetime.now().timestamp())

    def start(self, user):
        text = "Привет! Вот команды, которые можно использовать:\n\n"\
        		"save rating <твоё настроение> descr <пара слов о дне (можно не указывать)> - "\
        		"сохраняет сегодняшнее настроение\n\n"\
        		"rep - составляет отчёт о настроении за последний месяц\n\n"\
        		"ntf time <время уведомления> - "\
        		"устанавливает время для отправки напоминания\n\n"\
        		"reset - сбрасывает сегодняшнее настроение\n\n"\
        		"about - информация о приложении"

        self.send_message(user, text)


class Controller:
    def __init__(self, model, view):
        self.model = model
        self.view = view

    def handle_action(self, action, args):
        user = args.get("user", "unknown_user")

        if action == "start":
            self.view.start(user)
        elif action == "save":
            rating = int(args.get("rating"))
            if rating is None:
                raise Exception("Pass 'rating' key in args dict")

            description = args.get("descr", "")

            self.model.save_mood(user, rating, description)

            text = "Ваше настроение сегодня: " + str(rating)\
            	 + "\nПара слов о дне: " + description
            self.view.send_message(user, text)
        elif action == "rep":
            user_moods = self.model.get_user_moods_for_current_month(user)
            # Count stats
            self.view.send_report_to_user(user, report)
        elif action == "ntf":
            self.set_time_to_ask_question(user, new_time)
        elif action == "reset":
            self.model.reset_today_mood(user)
        elif action == "about":
        	self.view.about()
        # elif action == "exit":


if __name__ == "__main__":
    token = "413af2a20e7734a7bfc3768744c30cfaffdb92821ad32a6d0fa2d9b514011adbc49977b8a9927df961e41"
    vk_session = vk_api.VkApi(token=token)

    model = Model()
    view = View(vk_session)
    controller = Controller(model, view)

    for action, args in view.get_actions():
        controller.handle_action(action, args)

