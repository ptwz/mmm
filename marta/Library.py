from os import listdir
from os.path import isdir
from logging import getLogger, DEBUG
from re import compile, match
from Util import sorted_aphanumeric
#from watchdog.observers import Observer
#from watchdog.events import FileSystemEventHandler 
import eyed3
import os
import json

debug = getLogger('   Library').debug
getLogger('   Library').setLevel(DEBUG)


ALBUM_INDICATOR_FILE = ".albumindicator"

TAG_IN_PATH_REGEX = compile("^.*([0-9A-F]{12})$")

"""
class LibraryFSChangeHandler(FileSystemEventHandler):
    def __init__(self, library):
        self.library = library
        FileSystemEventHandler.__init__(self)

    def on_any_event(self, event):
        self.library.prepare()
"""

class Song(object):
    def __init__(self, path):
        """
        >>> s = Song("../audio/system/startup.mp3")

        >>> s is not None
        True
        >>> s.path
        '../audio/system/startup.mp3'
        >>> s.artist
        ''
        >>> s = Song("../audio/Bardic 012345678912/01 But All The Girls.mp3")
        >>> s.artist
        'Bardic'
        >>> s.track_num
        1
        """
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
        """
        >>> Album(".").name
        ''
        >>> a = Album("../audio/Bardic 012345678912")
        >>> album_song_count = len(a.songs)
        >>> album_song_count
        15
        >>> a._cur_song is None
        True
        >>> a.cur_song().track_num
        1
        >>> a.next_song().track_num
        2
        >>> a.next_song().track_num
        3
        >>> a.restart()
        >>> a.cur_song().track_num
        1
        >>> first_song = a.cur_song()
        >>> a.restart()
        >>> for i in range(0, album_song_count+1): print(a.next_song(wrap=False))
        None
        ...
        >>>
        """
        self.path = path

        self.tag = None
        self.name = ""
        self.artist = ""
        self._cur_song = None
        self.is_current_album = False
        self.songs = []

        self._song_idx = 0

        if not match(TAG_IN_PATH_REGEX, path):
            #raise Exception("naming convention error: " + current)
            debug("No tag for album path {}".format(path))
            self.tag = None
        else:
            self.tag = path[-12:]

        files = sorted_aphanumeric(listdir(path))
        mp3s = [ x for x in files if ".mp3" in x.lower() ]
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

    def restart(self):
        self._song_idx = 0
        self._cur_song = self.songs[self._song_idx]

    def next_song(self, wrap=True):
        """
        Returns the next song from this album.

        >>> a = Album("../audio/Bardic 012345678912")
        >>> a.next_song().track_num
        2
        >>> first_song = a.cur_song()
        >>> song_count = 0
        >>> while a.next_song(wrap=True) is not first_song: song_count += 1 # It wraps around, if instructed to do
        >>> song_count
        14
        """
        bumped = False
        if not self.songs:
            return None

        self._song_idx = self._song_idx + 1
        if self._song_idx >= len(self.songs):
            self._song_idx = 0
            if not wrap:
                bumped = True
        
        self._cur_song = self.songs[self._song_idx]
        if not bumped:
            return self._cur_song
        else:
            return None

    def prev_song(self, wrap=True):
        """
        Returns the next song from this album.

        >>> a = Album("../audio/Bardic 012345678912")
        >>> _foo = a.next_song()
        >>> a.prev_song().track_num
        1
        >>> first_song = a.cur_song()
        >>> song_count = 0
        >>> while a.prev_song(wrap=True) is not first_song: song_count += 1 # It wraps around, if instructed to do
        >>> song_count
        14
        """
        bumped = False
        if not self.songs:
            return None

        self._song_idx = self._song_idx - 1
        if self._song_idx < 0:
            if wrap:
                self._song_idx = len(self.songs)-1;
            else:
                self._song_idx = 0
                bumped = True
        
        self._cur_song = self.songs[self._song_idx]
        if not bumped:
            return self._cur_song
        else:
            return None

    def cur_song(self):
        """
        Returns the song the given album is currently playing

        >>> a = Album("../audio/Bardic 012345678912")
        >>> a.cur_song().track_num
        1
        """
        if self._cur_song is None:
            self.restart()
        return self._cur_song


class Playlist(object):
    _playlists_by_tag = {}

    @classmethod
    def get_playlist(cls, tag):
        try:
            return cls._playlists_by_tag[tag]
        except KeyError:
            return None

    def __init__(self, path):
        self.tag = None
        self._album_idx = None
        self._cur_album = None
        self.albums = []

        if not match(TAG_IN_PATH_REGEX, path):
            #raise Exception("naming convention error: " + current)
            debug("No tag for path {}".format(path))
            self.tag = None
        else:
            self.tag = path[-12:]

        files = listdir(path)

        # When there are mp3 files, assume this is an album and therefore
        # make only a small playlist from it
        if any(["mp3" == f.lower()[-3:] for f in files]):
            album = Album(path)
            self.albums = [ album ]
            if album.tag is not None:
                self.tag = album.tag
        else:
            for d in files:
                current = path + "/" + d

                if not isdir(current):
                    # We assume only one lever of playlists, so skip
                    debug("Ignoring file {} in playlist {}, will only look for album directories here.".format(d, path))

                album = Album(current)

                self.albums.append(album)

        # Remember all playlists by their tag
        if self.tag in self._playlists_by_tag:
            raise Exception("tag found twice: " + path + ", " + str(self._playlists_by_tag[self.tag]))

        self._playlists_by_tag[self.tag] = self
        self.albums = sorted(self.albums, key=lambda x: x.name.lower())

        self._album_idx = 0
        # Try to remember which album was played last
        current_albums = [x.is_current_album for x in self.albums]
        if True in current_albums:
            self._album_idx = current_albums.index(current_album_dir)

        self._cur_album = self.albums[self._album_idx]
    
    def _save_state(self):
        state = {"idx":self._album_idx}

        with open(self.path+"/playlist.json", "w") as f:
            json.dump(state, f)
    
    def _load_state(self):
        try:
            with open(self.path+"/playlist.json", "r") as f:
                state = json.load(f)
                self._album_idx = state["idx"]
        except:
            self.restart()
            return

        self._cur_album = self.albums[self._album_idx]

    def restart(self):
        self._album_idx = 0

        for album in self.albums:
            album.restart()

        if not self.albums:
            self._album_idx = None
            self._cur_album = None
        else:
            self._cur_album = self.albums[self._cur_album]

    def next_album(self, wrap=True):
        self._album_idx += 1
        if self._album_idx >= len(self.albums) and self.flag_repeat or wrap:
            self.album_idx = 0
        else:
            return None
        self._cur_album = self.albums[self._album_idx]
        return self._cur_album

    def prev_album(self, wrap=True):
        self._album_idx -= 1
        if self._album_idx < 0 and wrap:
            self.album_idx = len(self.albums)-1
        else:
            return None
        self._cur_album = self.albums[self._album_idx]
        return self._cur_album

    def next_song(self, wrap=True):
        if self._cur_album is None:
            return None

        song = self._cur_album.next_song(wrap)
        if song:
            return song
        album = self.next_album()
        if album:
            self._cur_album = album
            album.restart()
            return self.next_song()
        else:
            return None

    def prev_song(self, wrap=True):
        if self._cur_album is None:
            return None

        song = self._cur_album.prev_song(wrap)
        if song:
            return song
        album = self.prev_album()
        if album:
            self._cur_album = album
            album.restart()
            return self.prev_song(wrap)
        else:
            return None
    
    def cur_song(self):
        if self._cur_album is None:
            return None

        song = self._cur_album.cur_song()
        return song


class Library(object):

    def __init__(self, audio_path):
        self.audio_path = audio_path

        self.playlists = {}
        
        #change_handler = LibraryFSChangeHandler(self)

        #self._observer = Observer()
        #self._observer.schedule(change_handler, audio_path, recursive=True)
        #self._observer.start()

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

            playlist = Playlist(current)

    def lookup_playlist(self, tag):
        return Playlist.get_playlist(tag)

if __name__ == "__main__":
    from SetupLogging import setup_stdout_logging
    from sys import argv

    #setup_stdout_logging()

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
