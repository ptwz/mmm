from os import listdir
from os.path import isdir
from logging import getLogger
from re import compile, match
from Util import sorted_aphanumeric
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler 
import eyed3
import os

debug = getLogger('   Library').debug

ALBUM_INDICATOR_FILE = ".albumindicator"

TAG_IN_PATH_REGEX = compile("^.*([0-9A-F]{12})$")

class LibraryFSChangeHandler(FileSystemEventHandler):
    def __init__(self, library):
        self.library = library
        FileSystemEventHandler.__init__(self)

    def on_any_event(self, event):
        self.library.prepare()

class Song(object):
    def __init__(self, path):
        mp3 = eyed3.load(path)

        if mp3 is None:
            raise ValueError("File {} does not seem to be a valid MP3")
        
        self.current_position = None
        self.path = path

        if mp3.tag is None:
            # Fallback if no ID3 available
            (dirname, self.title) = os.path.split(path)
            (dirname, self.album) = os.path.split(dirname)
            self.artist = ""
            self.track_num = None
        else:
            self.title = mp3.tag.title
            self.artist = mp3.tag.artist
            self.album = mp3.tag.album
            self.track_num = mp3.tag.track_num[0]

    def __repr__(self):
        return("Song(title={}, track_num={})".format(self.title, self.track_num))

    def __str__(self):
        return("Song(title={}, track_num={})".format(self.title, self.track_num))

class Album(object):
    def __init__(self, path):
        self.path = path

        self.tag = None
        self.name = ""
        self.artist = ""
        self.current_song = None
        self.current_song_index = None
        self.is_current_album = False
        self.songs = []

        if not match(TAG_IN_PATH_REGEX, path):
            #raise Exception("naming convention error: " + current)
            debug("No tag for album path {}".format(path))
            self.tag = None
        else:
            self.tag = path[-12:]

        files = sorted_aphanumeric(listdir(path))
        mp3s = [ x for x in files if "mp3" in x.lower() ]
        if not mp3s:
            debug("empty album: " + path)
            return

        if ALBUM_INDICATOR_FILE in files:
            self.is_current_album = True 

        for filename in mp3s:
            current = self.path + "/" + filename

            if isdir(current):
                raise Exception("directory ended in .mp3 : " + current)
            
            try:
                song = Song(current)
                self.songs.append(song)
            except ValueError:
                song = None

        # Perfer sorting by track number from ID3,
        # otherwise resort to name based sorting
        if None not in [x.track_num for x in self.songs]:
            self.songs = sorted(self.songs, key=lambda x: x.track_num)
        else:
            self.songs = sorted(self.songs, key=lambda x: x.path)

        self.artist = self.songs[0].artist
        self.name = self.songs[0].album

    def __repr__(self):
        return("Album(tag={}, name={}, artist={}, songs={})".format(self.tag, self.name, self.artist, self.songs))

    def __str__(self):
        return("==========\nAlbum:\n tag:{}\n name:{}\n artist:{}\n: songs:{})".format(self.tag, self.name, self.artist, self.songs))

class Library(object):

    def __init__(self, audio_path):
        self.audio_path = audio_path
        self.TAG_TO_DIR = {}
        
        change_handler = LibraryFSChangeHandler(self)

        self._observer = Observer()
        self._observer.schedule(change_handler, audio_path, recursive=True)
        self._observer.start()

        self.prepare()


#    def _prepare_albums(self, tag_path):
        # we have to sahift and cannot simply insert in place at index 0 because that doesn't rotate the other entries
        # Album sort within a tag dir, disregard for now. Left in as a reminder
        #i = self.albums
        #if current_album_dir is not None:
        #    i = albums.index(current_album_dir)
        #    albums = albums[i:] + albums[:i]

    def prepare(self):
        self.TAG_TO_DIR = {}

        audio_path = self.audio_path

        if not isdir(audio_path):
            debug("not a directory: " + audio_path)
            exit(1)

        if not isdir(audio_path + "/system"):
            raise Exception("missing directory: " + audio_path + "/system")

        dirs = listdir(audio_path)

        debug(audio_path + "/system exists")

        for d in dirs:

            current = audio_path + "/" + d

            debug(d)
            if not isdir(audio_path + "/" + d):
                raise Exception("not a directory: " + current)

            if d == "system":
                continue

            album = Album(current)

            if album.tag is not None:
                if album.tag in self.TAG_TO_DIR:
                    raise Exception("tag found twice: " + d + ", " + str(self.TAG_TO_DIR[tag]))
                self.TAG_TO_DIR[album.tag] = album
                #debug(album.tag + "=" + str(self.TAG_TO_DIR[album.tag]))

    def lookup_album(self, tag):
        return self.TAG_TO_DIR[tag]

if __name__ == "__main__":
    from SetupLogging import setup_stdout_logging
    from sys import argv

    setup_stdout_logging()

    if len(argv) != 2:
        debug("Error: Missing path argument.")
        exit(1)

    lib = Library(argv[1])
    debug(str(lib.TAG_TO_DIR))
    #try:
    #    lib = Library(argv[1])
    #    input()
    #except Exception as e:
    #    debug("Error: " + repr(e))
    #    exit(1)

    debug("Everything seems fine.")
    exit(0)
