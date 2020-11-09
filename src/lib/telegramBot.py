import logging
import os

from telegram.ext import CommandHandler, ConversationHandler, CallbackQueryHandler
from telegram.ext import Updater

from lib import command, botStates, botEvents, utils, bot_utils, snapshot_command

logger = logging.getLogger(os.path.basename(__file__))


class TelegramBot:
    def __init__(self, config, auth_chat_ids):
        # Constructor
        self.config = config
        self.auth_chat_ids = auth_chat_ids
        self.updater = Updater(token=config["token"], use_context=True)
        self.bot = self.updater.bot
        self.dispatcher = self.updater.dispatcher

        # Commands
        self.utils = bot_utils.BotUtils(config, auth_chat_ids, self.bot)
        self.command = command.Command(config, auth_chat_ids, self.utils)
        self.snapshot = snapshot_command.SnapshotCommand(config, auth_chat_ids, self.utils)

        # FSM
        self.settings_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.command.toggle, pattern='^' + str(botEvents.TOGGLE_CLICK) + '$'),
                          CallbackQueryHandler(self.command.get_log, pattern='^' + str(botEvents.LOG_CLICK) + '$'),
                          CallbackQueryHandler(self.command.face_number,
                                               pattern='^' + str(botEvents.FACES_CLICK) + '$'),
                          CallbackQueryHandler(self.command.seconds_to_analyze,
                                               pattern='^' + str(botEvents.SECONDS_CLICK) + '$'),
                          CallbackQueryHandler(self.command.frame_percentage,
                                               pattern='^' + str(botEvents.PERCENTAGE_CLICK) + '$'),
                          ],
            states={
                botStates.RESP_SETTINGS: [
                    CallbackQueryHandler(self.command.setting_resp, pattern="^(?!" + str(botEvents.BACK_CLICK) + ").*")]
            },
            fallbacks=[CallbackQueryHandler(self.command.exit, pattern='^' + str(botEvents.EXIT_CLICK) + '$'),
                       CallbackQueryHandler(self.command.show_settings, pattern='^' + str(botEvents.BACK_CLICK) + '$')],
            per_message=True,
            map_to_parent={
                botStates.END: botStates.LOGGED,
                botStates.SETTINGS: botStates.SETTINGS
            }
        )

        # Level 1 only callback (no warning)
        self.menu_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.command.show_settings, pattern='^' + str(botEvents.SETTINGS_CLICK) + '$'),
            ],
            states={
                botStates.SETTINGS: [self.settings_handler]
            },
            fallbacks=[CallbackQueryHandler(self.command.exit, pattern='^' + str(botEvents.EXIT_CLICK) + '$')],
            per_message=True,
            map_to_parent={
                botStates.END: botStates.LOGGED,
                botStates.LOGGED: botStates.LOGGED,
                botStates.NOT_LOGGED: botStates.NOT_LOGGED
            }
        )

        self.snapshot_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.snapshot.snapshot_resp, pattern="^(?!" + str(botEvents.EXIT_CLICK) + ").*")],
            states={},
            fallbacks=[CallbackQueryHandler(self.command.exit, pattern='^' + str(botEvents.EXIT_CLICK) + '$')],
            per_message=True,
            map_to_parent={
                botStates.LOGGED: botStates.LOGGED,
                botStates.NOT_LOGGED: botStates.NOT_LOGGED
            }
        )

        # Level 0
        self.conversationHandler = ConversationHandler(
            entry_points=[CommandHandler('start', callback=self.command.start)],
            states={
                botStates.NOT_LOGGED: [CommandHandler('start', callback=self.command.start)],
                botStates.LOGGED: [CommandHandler('menu', callback=self.command.show_logged_menu),
                                   CommandHandler('snapshot', callback=self.snapshot.show_snapshot),
                                   self.menu_handler, self.snapshot_handler],
            },
            fallbacks=[CallbackQueryHandler(self.command.exit, pattern='^' + str(botEvents.EXIT_CLICK) + '$')]
        )
        # Init handlers
        self.dispatcher.add_handler(self.conversationHandler)

    def start_web_hook(self):
        # START WEBHOOK
        network = self.config["network"]["telegram"]
        key = utils.get_project_relative_path(network["key"])
        cert = utils.get_project_relative_path(network["cert"])
        utils.start_web_hook(self.updater, self.config["token"], network["ip"], network["port"], key, cert)
        logger.info("Started Webhook bot")

    def start_polling(self):
        logger.info("Started Polling bot")
        self.updater.start_polling()

    def get_bot(self):
        return self.bot

    def send_image_to_logged_users(self, image):
        logged_users = dict((k, v) for k, v in self.auth_chat_ids.items() if v["active"] is True)
        for chatId, value in logged_users.items():
            self.bot.send_photo(chatId, image)

    def send_msg_to_logged_users(self, msg):
        logged_users = dict((k, v) for k, v in self.auth_chat_ids.items() if v["active"] is True)
        for chatId, value in logged_users.items():
            self.bot.send_message(chatId, text=msg)
