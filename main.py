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
            json.dump(self.storage, file)

    def __init__(self):
        self.storage = collections.defaultdict(dict)

        self.__load_storage()

    def save_mood(self, user, rating: int, description: str):
        self.storage[user][str(datetime.datetime.now().date())] = (rating, description)

        self.__save_storage()
        print(self.storage, flush=True)



class View:
    def __init__(self, vk_session):
        self.vk_session = vk_session

    def __parse_message(self, text):
        action = text.split()[0]
        keys = text.split()[1::2]
        values = text.split()[2::2]
        args = dict(zip(keys, values))
        return action, args

    def get_actions(self):
        longpoll = VkLongPoll(self.vk_session)
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text:
                action, args = self.__parse_message(event.text)
                print(event.from_id, flush=True)

                yield (action, args)

    def about(self):

        vk = self.vk_session.get_api()
        vk.messages.send(user_id=id,message="Hello!")

class Controller:
    def __init__(self, model, view):
        self.model = model
        self.view = view

    def handle_action(self, action, args):
        user = args.get("user", "unknown_user")

        if action == "start":
            self.view.about()
        elif action == "save":
            rating = int(args.get("rating"))
            if rating is None:
                raise Exception("Pass 'rating' key in args dict")

            description = args.get("description", "")

            self.model.save_mood(user, rating, description)
        elif action == "rep":
            user_moods = self.model.get_user_moods_for_current_month(user)
            # Count stats
            self.view.send_report_to_user(user, report)
        elif action == "ntf":
            self.set_time_to_ask_question(user, new_time)
        elif action == "reset":
            self.model.reset_today_mood(user)
        elif action == "show_menu":
            self.view.show_menu()
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

