# system
from logging import handlers, getLogger, DEBUG, INFO, Formatter, StreamHandler
from sys import stdout, argv
from queue import Queue, Empty
from time import sleep, strftime
from signal import signal, SIGINT
from os import environ
from monotonic import monotonic as mtime
import traceback
import os
import pwd

import Buttons
from MartaHandler import MartaHandler
from LEDStrip import LEDStrip
from MPG123 import MPG123Player
from MPU import MPU
from RFIDReader import RFIDReader
from TagToHandler import TAG_TO_HANDLER
from Library import Library, LibraryAPI
from Web import WebServer
from EventManager import Server, QueueManager

debug = getLogger('     Marta').debug
info = getLogger('     Marta').info

MARTA_BASE_DIR = environ["MARTA"]


class Marta(object):
    ################
    # EVENTS
    EVENT_SONG_STOPPED = 0
    EVENT_RFID_TAG = 1
    EVENT_BUTTON = 2
    EVENT_MPG123_ERROR = 3
    EVENT_ROTATION = 4
    EVENT_INTERRUPT = 5
    EVENT_WEB_MUSIC = 6
    EVENT_WEB_POWER = 7
    EVENT_WEB_RFID = 8

    EXIT_DEBUG = 2

    EVENT_HUMAN_READABLE = [
        "EVENT_SONG_STOPPED",
        "EVENT_TAG",
        "EVENT_BUTTON",
        "EVENT_MPG123_ERROR",
        "EVENT_ROTATION",
        "EVENT_INTERRUPT",
        "EVENT_WEB_MUSIC",
        "EVENT_WEB_POWER",
        "EVENT_WEB_RFID"
    ]

    ################
    # SPECIAL TAGS

    INTERRUPT_TAG = "5600C7AC4B76"

    ################
    # AUDIO

    START_SOUND_PATH = MARTA_BASE_DIR + "/audio/system/startup.mp3"
    SHUTDOWN_SOUND_PATH = MARTA_BASE_DIR + "/audio/system/shutdown.mp3"
    SYSTEM_SOUND_VOLUME = 2

    def __init__(self, username):

        library_api_web = LibraryAPI()
        self.library = Library(MARTA_BASE_DIR + "/audio/")
        self.library_api = LibraryAPI(self.library)

        self.__queue_manager = QueueManager.manager()

        self.__message_queue = self.__queue_manager.get_marta()

        self.leds = LEDStrip()
        Buttons.setup_gpio(lambda pin, millis: self.__message_queue.put([Marta.EVENT_BUTTON, pin, millis]))

        if Buttons.is_pushed(Buttons.POWER_BUTTON) and Buttons.is_pushed(Buttons.RED_BUTTON):
            Buttons.terminate()
            info("Early user interrupt!")
            exit(Marta.EXIT_DEBUG)

        self.player = MPG123Player(lambda: self.__message_queue.put([Marta.EVENT_SONG_STOPPED]),
                                   lambda: self.__message_queue.put([Marta.EVENT_MPG123_ERROR]),
                                   volume=Marta.SYSTEM_SOUND_VOLUME)


        self.player.load_track_from_file(Marta.START_SOUND_PATH)
        self.leds.startup()
        self.player.play_track()

        # hacky because MPG123Player is async
        while not self.player.is_track_playing():
            sleep(0.05)

        # True = GPIO.HIGH = 1
        # False = GPIO.LOW = 0
        g = True
        while self.player.is_track_playing():
            Buttons.set_status_led(g)
            sleep(0.2)
            g = not g

        Buttons.set_status_led(0)

        # Empty q after short period of time (player stop event and button pushes)
        sleep(0.1)
        while not self.__message_queue.empty():
            self.__message_queue.get(block=False)

        self.mpu = MPU(period=1, threshold=5,
                       rotation_receiver=lambda x, y: self.__message_queue.put([Marta.EVENT_ROTATION, x, y]))

        self.rfid_reader = RFIDReader(lambda tag: self.__message_queue.put([Marta.EVENT_RFID_TAG, tag]))


    def interrupt(self):
        self.__message_queue.put([Marta.EVENT_INTERRUPT])

    def message_loop(self):

        current_handler = TAG_TO_HANDLER["default"].get_instance(self)
        max_mono_time = mtime() + current_handler.initialize()

        while True:
            now = mtime()
            debug("now = " + str(now))

            if now >= max_mono_time:
                debug("timeout occurred")
                break

            timeout = max_mono_time - now
            debug("waiting for " + str(timeout))
            try:
                msg = self.__message_queue.get(block=True, timeout=timeout)
            except Empty:
                # If a time change (due to network time availability) occurs while waiting for an event,
                # Queue.get will return Empty early:

                # 14:46:31.368 | main | now = 54.502526
                # 14:46:31.380 | main | waiting for 299.955775
                # -- NOW THE TIME CHANGE OCCURS --
                # 19:29:13.403 | main | timeout @ 67.323505
                # 19:29:13.410 | main | Terminating!

                # Instead of breaking here, we just continue, because we have another check on top of this function
                #  which checks the timeout again but using a monotonic timer
                debug("possible timeout @ " + str(mtime()))
                continue

            event = msg[0]
            params = msg[1:]

            if event == Marta.EVENT_INTERRUPT:
                info("Critical: Interrupt event!")
                break

            elif event == Marta.EVENT_MPG123_ERROR:
                info("Critical: MPG123 error event!")
                break

            elif event == Marta.EVENT_BUTTON and params[0] == Buttons.POWER_BUTTON:
                info("Critical: Power button event!")
                break

            elif event == Marta.EVENT_RFID_TAG:
                tag = params[0]

                if tag == Marta.INTERRUPT_TAG:
                    info("Critical: Interrupt tag event!")
                    exit(Marta.EXIT_DEBUG)
                    break

                if tag in TAG_TO_HANDLER:
                    current_handler.uninitialize()
                    current_handler = TAG_TO_HANDLER[tag].get_instance(self)
                    current_handler.initialize()

            debug(Marta.EVENT_HUMAN_READABLE[event] + ": " + str(params))
            if event == Marta.EVENT_ROTATION:
                return_val = current_handler.rotation_event(params[0], params[1])
            elif event == Marta.EVENT_SONG_STOPPED:
                return_val = current_handler.player_stop_event()
            elif event == Marta.EVENT_RFID_TAG:
                return_val = current_handler.rfid_tag_event(params[0])
            elif event == Marta.EVENT_BUTTON:
                return_val = current_handler.button_event(params[0], params[1])
            elif event == Marta.EVENT_WEB_MUSIC:
                music_handler = TAG_TO_HANDLER["default"].get_instance(self)
                music_hanlder.web_command(params)
                # self. HIER BAUSTELLE
                return_val = None
            else:
                raise Exception("Unknown event: " + str(event))

            if return_val is None:
                debug("not changing the timeout")
            else:
                if return_val == MartaHandler.EVENT_HANDLER_DONE:
                    debug("This event handler is done.")
                    current_handler.uninitialize()
                    current_handler = TAG_TO_HANDLER["default"].get_instance(self)
                    return_val = current_handler.initialize()
                max_mono_time = mtime() + return_val

        current_handler.uninitialize()

    def terminate(self):
        info("Terminating!")

        try:
            self.player.set_volume(Marta.SYSTEM_SOUND_VOLUME)
            self.player.set_pitch(100)
            self.player.load_track_from_file(Marta.SHUTDOWN_SOUND_PATH)
            self.player.play_track()
        except:
            pass

        try:
            self.leds.shutdown()
        except:
            pass

        try:
            for i in range(20):
                Buttons.set_status_led(i % 2)
                sleep(0.2)
        except:
            pass

        try:
            self.mpu.terminate()
        except:
            pass

        try:
            self.player.terminate()
        except:
            pass

        try:
            self.rfid_reader.terminate()
        except:
            pass

        try:
            self.leds.terminate()
        except:
            pass

        try:
            for i in range(10):
                Buttons.set_status_led(i % 2)
                sleep(0.2)
        except:
            pass

        try:
            Buttons.terminate()
        except:
            pass


def main():
    queueserver = Server()
    queueserver.start()
    sleep(1)
    qm = QueueManager.manager()

    logger = getLogger('')
    logger.setLevel(INFO)
    formatter = Formatter("%(asctime)s.%(msecs)03d | %(name)s |    %(message)s", "%H:%M:%S")

    if "log2stdout" in argv:
        logger.setLevel(DEBUG)
        ch = StreamHandler(stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    fh = handlers.RotatingFileHandler(MARTA_BASE_DIR + "/logs/mmm.log", maxBytes=(1024 * 1024 * 10), backupCount=10)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    info("#################################################")
    info("#                  INITIALIZED                  #")
    info("#              " + strftime("%Y-%m-%d %H:%M:%S") + "              #")
    info("#################################################")

    info("""

                            _    _        _                                _
                           | |  | |      | |                              | |
                           | |  | |  ___ | |  ___  ___   _ __ ___    ___  | |_  ___
                           | |/\| | / _ \| | / __|/ _ \ | '_ ` _ \  / _ \ | __|/ _ \
                           \  /\  /|  __/| || (__| (_) || | | | | ||  __/ | |_| (_) |
                            \/  \/  \___||_| \___|\___/ |_| |_| |_| \___|  \__|\___/



    MMMMMMMM               MMMMMMMM     MMMMMMMM               MMMMMMMM     MMMMMMMM               MMMMMMMM
    M:::::::M             M:::::::M     M:::::::M             M:::::::M     M:::::::M             M:::::::M
    M::::::::M           M::::::::M     M::::::::M           M::::::::M     M::::::::M           M::::::::M
    M:::::::::M         M:::::::::M     M:::::::::M         M:::::::::M     M:::::::::M         M:::::::::M
    M::::::::::M       M::::::::::M     M::::::::::M       M::::::::::M     M::::::::::M       M::::::::::M
    M:::::::::::M     M:::::::::::M     M:::::::::::M     M:::::::::::M     M:::::::::::M     M:::::::::::M
    M:::::::M::::M   M::::M:::::::M     M:::::::M::::M   M::::M:::::::M     M:::::::M::::M   M::::M:::::::M
    M::::::M M::::M M::::M M::::::M     M::::::M M::::M M::::M M::::::M     M::::::M M::::M M::::M M::::::M
    M::::::M  M::::M::::M  M::::::M     M::::::M  M::::M::::M  M::::::M     M::::::M  M::::M::::M  M::::::M
    M::::::M   M:::::::M   M::::::M     M::::::M   M:::::::M   M::::::M     M::::::M   M:::::::M   M::::::M
    M::::::M    M:::::M    M::::::M     M::::::M    M:::::M    M::::::M     M::::::M    M:::::M    M::::::M
    M::::::M     MMMMM     M::::::M     M::::::M     MMMMM     M::::::M     M::::::M     MMMMM     M::::::M
    M::::::M               M::::::M     M::::::M               M::::::M     M::::::M               M::::::M
    M::::::M               M::::::M     M::::::M               M::::::M     M::::::M               M::::::M
    M::::::M               M::::::M     M::::::M               M::::::M     M::::::M               M::::::M
    MMMMMMMM               MMMMMMMM     MMMMMMMM               MMMMMMMM     MMMMMMMM               MMMMMMMM

    """)

    exit_val = 0

    debug("initializing")
    marta = Marta("pi")
    signal(SIGINT, lambda s, f: marta.interrupt())

    debug("looping")
    try:
        marta.message_loop()
    except Exception as e:
        print("excepted: " + str(e))
        print(traceback.format_exc())
        exit_val = 1

    marta.terminate()

    debug("exiting")
    exit(exit_val)


if __name__ == "__main__":
    
    main()
