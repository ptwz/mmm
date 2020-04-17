from logging import getLogger
from os import listdir, environ, remove

import Buttons
from Util import sorted_aphanumeric
from LEDStrip import LEDStrip
from MartaHandler import MartaHandler
from os.path import exists

debug = getLogger('MscHandler').debug

MARTA_BASE_DIR = environ["MARTA"]


class MusicHandler(MartaHandler):
    PITCHES = [55, 70, 85, 100, 115, 130, 145, 160, 175, 190]
    DEFAULT_PITCH = 100

    VOLUMES = [1, 2, 3, 5, 7, 9, 12, 15, 18, 22]
    DEFAULT_VOLUME = 1

    BRIGHTNESSES = [0, 28, 56, 84, 112, 140, 168, 196, 224, 255]
    DEFAULT_BRIGHTNESS = 255

    CONTROL_PITCH = 0
    CONTROL_VOLUME = 1
    CONTROL_BRIGHTNESS = 2

    SONG_DIR = MARTA_BASE_DIR + "/audio/"
    UNKNOWN_TAG_FILE = SONG_DIR + "/unknown_tag.txt"

    SONG_STATE_FILE = ".songstate"

    LONG_TIMEOUT = 20 * 60
    SHORT_TIMEOUT = 5 * 60

    LONG_CLICK_THRESHOLD = 1500

    #################
    # SINGLETON
    instance = None

    @staticmethod
    def get_instance(marta):
        if MusicHandler.instance is None:
            MusicHandler.instance = MusicHandler(marta)
        return MusicHandler.instance

    #################

    def __init__(self, marta):
        super(MusicHandler, self).__init__(marta)
        self.currently_controlling = MusicHandler.CONTROL_VOLUME
        self.current_tag = None
        self.expected_stop = False

        if exists(MusicHandler.UNKNOWN_TAG_FILE):
            debug("unknown tag file exists. removing")
            remove(MusicHandler.UNKNOWN_TAG_FILE)

        # TODO: Neccessary??
        #self.marta.library.prepare(MusicHandler.SONG_DIR)

    def initialize(self):
        debug("init")
        return MusicHandler.SHORT_TIMEOUT

    def save_state_and_stop(self):
        self.marta.player.pause_track()

        if self.current_playlist:
            debug("Saving state.")
            self.current_playlist.save_state(position=self.marta.player.get_position_in_millis())

        self.expected_stop = True
        self.marta.player.stop_track()

    def load_state(self, tag):
        debug("Loading state.")

        playlist = self.marta.library.lookup_playlist(tag)
        playlist.load_state()

        if playlist is None:
            debug("Unkown tag read...")
            return

        self.current_tag = tag
        self.current_playlist = playlist
        debug("tag name: " + self.current_playlist.name)

        return playlist.cur_pos()

    def show_playlist_progress(self):
        if not self.current_playlist:
            self.marta.leds.fade_up_and_down(LEDStrip.RED)
            return

        song_count = self.current_playlist.count_songs()
        current_song = self.current_playlist.current_song_index()
        if song_count == 1:
            self.marta.leds.fade_up_and_down(LEDStrip.GREEN)
        else:
            self.marta.leds.song(current_song, song_count)

    def rfid_removed_event(self):
        debug("tag removed.")
        self.marta.leds.fade_up_and_down(LEDStrip.RED)
        self.save_state_and_stop()
        return MusicHandler.SHORT_TIMEOUT

    def _play_currently_selected_song(self, current_position = 0):
        if not self.current_playlist:
            debug("Tried to play without a playlist?!")
            return

        cur_song = self.current_playlist.cur_song()

        if self.marta.player.is_track_playing():
            self.expected_stop = True
            self.marta.player.stop_track()

        self.marta.player.load_track_from_file(cur_song.path)
        if current_position != 0:
            self.marta.player.set_position_in_millis(current_position)

        self.show_playlist_progress()

        self.marta.player.play_track()

    def rfid_music_tag_event(self, tag):
        current_position = self.load_state(tag)
        self._play_currently_selected_song(current_position)

        return MusicHandler.LONG_TIMEOUT

    def rfid_tag_event(self, tag):
        debug("tag=%s", tag)

        if tag is None:
            if self.current_tag is None:
                debug("probably removed unknown tag")

                if exists(MusicHandler.UNKNOWN_TAG_FILE):
                    debug("unknown tag file exists. removing")
                    remove(MusicHandler.UNKNOWN_TAG_FILE)

                self.marta.leds.fade_up_and_down(LEDStrip.RED)
                return MusicHandler.SHORT_TIMEOUT

            return self.rfid_removed_event()

        if self.marta.library.lookup_playlist(tag) is None:
            self.current_song_dir = None
            debug("unknown tag")

            with open(MusicHandler.UNKNOWN_TAG_FILE, "w") as unknown_tag_file:
                debug("writing to unknown tag file")
                unknown_tag_file.write(tag)

            self.marta.leds.fade_up_and_down(LEDStrip.ORANGE)
            return MusicHandler.LONG_TIMEOUT

        return self.rfid_music_tag_event(tag)

    def rotation_event(self, x, y):
        debug("rotation event!")
        if x < -45:
            if self.currently_controlling == MusicHandler.CONTROL_BRIGHTNESS:
                return

            self.currently_controlling = MusicHandler.CONTROL_BRIGHTNESS
            self.marta.leds.fade_up_and_down(LEDStrip.PURPLE)
            debug("now controlling brightness")
            return

        if x > 45:
            if self.currently_controlling == MusicHandler.CONTROL_PITCH:
                return

            self.currently_controlling = MusicHandler.CONTROL_PITCH
            self.marta.leds.fade_up_and_down(LEDStrip.YELLOW)
            debug("now controlling pitch")
            return

        if self.currently_controlling == MusicHandler.CONTROL_VOLUME:
            return

        self.currently_controlling = MusicHandler.CONTROL_VOLUME
        self.marta.leds.fade_up_and_down(LEDStrip.BLUE)
        debug("now controlling volume")

    def player_stop_event(self):
        '''
        Called when a song stopped playing, reported by MPG123
        '''
        if self.expected_stop:
            self.expected_stop = False
            debug("ignoring this event because stopping is expected")
            return

        if not self.current_playlist:
            debug("Song stopped without an active playlist?!")
            return

        cur_song = self.current_playlist.next_song()

        self.show_playlist_progress()

        self.marta.player.load_track_from_file(cur_song.path)
        self.marta.player.play_track()

    def button_red_green_event(self, pin, millis):
        if self.currently_controlling == MusicHandler.CONTROL_VOLUME:
            debug("change volume")
            arr = MusicHandler.VOLUMES
            current = self.marta.player.get_volume()
        elif self.currently_controlling == MusicHandler.CONTROL_PITCH:
            debug("change pitch")
            arr = MusicHandler.PITCHES
            current = self.marta.player.get_pitch()
        else:
            debug("change brightness")
            arr = MusicHandler.BRIGHTNESSES
            current = self.marta.leds.get_brightness()

        debug("current value: " + str(current))

        current = arr.index(current)

        if pin == Buttons.RED_BUTTON:
            new = current + 1
        else:
            new = current - 1

        if new < 0 or new >= len(arr):
            debug("would be out of bounds")
            self.marta.leds.volume(current)
            return

        self.marta.leds.volume(new)

        new = arr[new]
        debug("new value: " + str(new))

        if self.currently_controlling == MusicHandler.CONTROL_VOLUME:
            self.marta.player.set_volume(new)
        elif self.currently_controlling == MusicHandler.CONTROL_PITCH:
            self.marta.player.set_pitch(new)
        else:
            self.marta.leds.set_brightness(new)

    def button_next_previous_album(self, pin):
        tag = self.current_tag

        if pin == Buttons.YELLOW_BUTTON:
            cur_album = self.marta.library.next_album()
        else:
            cur_album = self.marta.library.prev_album()

        self._play_currently_selected_song()

    def button_next_previous_song(self, pin):
        if not self.current_playlist:
            return

        if pin == Buttons.BLUE_BUTTON: # Previous/Rewind
            pos = self.marta.player.get_position_in_millis()
            debug("pos=" + str(pos))

            # if we are at the beginning of a song, skip to the beginning
            if pos > 2000:
                self.marta.player.set_position_in_millis(0)
            else:
                self.current_playlist.prev_song()
                self._play_currently_selected_song()
        else:
            self.current_playlist.next_song()
            self._play_currently_selected_song()

        self.show_playlist_progress()

    def button_event(self, pin, millis):
        debug("pin: " + Buttons.BUTTONS_HUMAN_READABLE[pin])

        if pin == Buttons.YELLOW_BUTTON or pin == Buttons.BLUE_BUTTON:
            if self.current_tag is None:
                debug("no tag. ignore")
                return MusicHandler.SHORT_TIMEOUT

            if millis > MusicHandler.LONG_CLICK_THRESHOLD:
                self.button_next_previous_album(pin)
            else:
                self.button_next_previous_song(pin)
        elif pin == Buttons.GREEN_BUTTON or pin == Buttons.RED_BUTTON:
            self.button_red_green_event(pin, millis)

        if self.current_tag is None:
            return MusicHandler.SHORT_TIMEOUT
        else:
            return MusicHandler.LONG_TIMEOUT

    def uninitialize(self):
        debug("uninitialize")
        if self.current_tag is not None:
            self.save_state_and_stop()
