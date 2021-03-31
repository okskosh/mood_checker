import collections
import datetime
import json
import os
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id


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

    def __parse_event(self, event):
        action, args = self.__parse_message(event.text)
        args["user"] = event.user_id
        return action, args

    def get_actions(self):
        longpoll = VkLongPoll(self.vk_session)
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text:
                action, args = self.__parse_event(event)

                yield (action, args)

    def show_to_user(self, user, text):
    	self.vk.messages.send(user_id=user, message=text, random_id=get_random_id())

    def start(self, user):
        text = "Привет! Вот команды, которые можно использовать:\n\n"\
        		"save rating <твоё настроение> descr <пара слов о дне (можно не указывать)> - "\
        		"сохраняет сегодняшнее настроение\n\n"\
        		"rep - составляет отчёт о настроении за последний месяц\n\n"\
        		"ntf time <время уведомления> - "\
        		"устанавливает время для отправки напоминания\n\n"\
        		"reset - сбрасывает сегодняшнее настроение\n\n"\
        		"about - информация о приложении"

        self.show_to_user(user, text)


class Controller:
    def __init__(self, model, view):
        self.model = model
        self.view = view

    def __start(self, user, args):
        self.view.start(user)

    def __save(self, user, args):
        rating = int(args.get("rating"))
        if rating is None:
            raise Exception("Pass 'rating' key in args dict")

        description = args.get("descr", "")

        self.model.save_mood(user, rating, description)

        text = "Ваше настроение сегодня: " + str(rating)\
             + "\nПара слов о дне: " + description
        self.view.show_to_user(user, text)

    def __rep(self, user, args):
        user_moods = self.model.get_user_moods_for_current_month(user)
        # Count stats
        self.view.send_report_to_user(user, report)

    def __ntf(self, user, args):
        self.set_time_to_ask_question(user, new_time)

    def __reset(self, user, args):
        self.model.reset_today_mood(user)

    def __about(self, user, args):
        self.view.about()

    def __error(self, user):
        text = "Такой команды нет"
        self.view.show_to_user(user, text)

    def handle_action(self, action, args):
        user = args.get("user", "unknown_user")

        action_handler = {
            "start" : self.__start, 
            "save" : self.__save,
            "rep" : self.__rep,
            "ntf" : self.__ntf,
            "reset" : self.__reset,
            "about" : self.__about
        }

        def error_handler(user, args):
            self.__error(user)

        action_handler.get(action, error_handler)(user, args)
        

if __name__ == "__main__":
    token = "413af2a20e7734a7bfc3768744c30cfaffdb92821ad32a6d0fa2d9b514011adbc49977b8a9927df961e41"
    vk_session = vk_api.VkApi(token=token)

    model = Model()
    view = View(vk_session)
    controller = Controller(model, view)

    for action, args in view.get_actions():
        controller.handle_action(action, args)

