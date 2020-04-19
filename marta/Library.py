from os import listdir
from os.path import isdir
from logging import getLogger, DEBUG, INFO
from re import compile, match
from Util import sorted_aphanumeric
import hashlib
#from watchdog.observers import Observer
#from watchdog.events import FileSystemEventHandler
import eyed3
import os
import json

debug = getLogger('   Library').debug
info = getLogger('   Library').info

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

    @classmethod
    def from_file(cls, path):
        """
        >>> s = Song.from_file("../audio/system/startup.mp3")

        >>> s is not None
        True
        >>> s.path
        '../audio/system/startup.mp3'
        >>> s.artist
        ''
        >>> s = Song.from_file("../audio/Bardic 012345678912/01 But All The Girls.mp3")
        >>> s.artist
        'Bardic'
        >>> s.track_num
        1
        """
        mp3 = eyed3.load(path)

        if mp3 is None:
            raise ValueError("File {} does not seem to be a valid MP3")

        self = cls(path)
        self.current_position = None
        self.mtime = os.path.getmtime(path)

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

        return self

    @classmethod
    def from_dict(cls, d):
        """
        Creates a new Song instance from a given dict

        >>> song = Song.from_dict({"path":"../audio/MaxMustermann 12345", "artist": "Max Mustermann", "album": "Musteralbum", "title": "Oh Musterlied", "track_num":1})
        """
        return cls(**d)

    def __init__(self, path, title=None, album=None, artist=None, track_num=None, mtime=None):
        self.path = path
        self.title = title
        self.album = album
        self.artist = artist
        self.track_num = track_num
        self.mtime = mtime

    def __repr__(self):
        return("Song(title={}, track_num={})".format(self.title, self.track_num))

    def __str__(self):
        return("Song(title={}, track_num={})".format(self.title, self.track_num))

    def to_dict(self):
        return {
            "path": self.path,
            "title": self.title,
            "album": self.album,
            "artist": self.artist,
            "track_num": self.track_num,
            "mtime": self.mtime
            }

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
        """
        self.path = path
        self.id = hashlib.sha256(path.encode('utf-8')).hexdigest()

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
        self.rescan()
        self.load_state()

    def rescan(self):
        '''
        Scan album directory for files and load their metadata.
        '''
        # Load state cache
        cache_file = self.path+"/cache.json"
        cached_songs = {}
        if os.path.isfile(cache_file):
            try:
                with open(self.path + "/cache.json", 'r') as f:
                    cache = json.load(f)
                    for song_dict in cache:
                        song = Song.from_dict(song_dict)
                        cached_songs[song.path] = song
            except PermissionError:
                info("Could not read cache % due to lack of permissions" % cache)
            except json.JSONDecodeError:
                info("JSON format error reading cache file %" % cache)

        files = sorted_aphanumeric(listdir(self.path))
        mp3s = [ x for x in files if ".mp3" in x.lower() ]
        if not mp3s:
            info("empty album: " + self.path)
            return

        if ALBUM_INDICATOR_FILE in files:
            self.is_current_album = True

        for filename in mp3s:
            current = self.path + "/" + filename

            if isdir(current):
                raise Exception("directory ended in .mp3 : " + current)

            # Prefer cached songs
            if current in cached_songs:
                song = cached_songs[current]
                if os.path.getmtime(current) == song.mtime:
                    self.songs.append(song)
                    continue
                        
            try:
                song = Song.from_file(current)
                self.songs.append(song)
            except ValueError:
                song = None

        # Perfer sorting by track number from ID3,
        # otherwise resort to name based sorting
        if None not in [x.track_num for x in self.songs]:
            self.songs = sorted(self.songs, key=lambda x: x.track_num)
        else:
            self.songs = sorted(self.songs, key=lambda x: x.path)

        if not self.songs:
            info("No songs in directory...")
            return

        self.artist = self.songs[0].artist
        self.name = self.songs[0].album

        # Now write cache back
        with open(cache_file, 'w') as f:
            json.dump([song.to_dict() for song in self.songs], f)

    def __repr__(self):
        return("Album(tag={}, name={}, artist={}, songs={})".format(self.tag, self.name, self.artist, self.songs))

    def __str__(self):
        return("==========\nAlbum:\n tag:{}\n name:{}\n artist:{}\n: songs:{})".format(self.tag, self.name, self.artist, self.songs))

    def save_state(self, position=None):
        self._song_position = position
        state = {"idx":self._song_idx, "position": self._song_position}

        with open(self.path+"/album.json", "w") as f:
            json.dump(state, f)

    def load_state(self):
        try:
            with open(self.path+"/album.json", "r") as f:
                state = json.load(f)
                self._song_idx = state["idx"]
                self._song_position = state['position']
        except:
            self.restart()
            return

        self._cur_song = self.songs[self._song_idx]

    def to_dict(self):
        return {
                "name": self.name,
                "id": self.id,
                "path": self.path,
                "current_song": self._song_idx,
                "songs": [ s.to_dict() for s in self.songs ]
                }

    def restart(self):
        """
        Resets playback of album to its first song.

        >>> a = Album("../audio/Bardic 012345678912")
        >>> _ = a.next_song()
        >>> a.cur_song().track_num
        2
        >>> a.restart()
        >>> a.cur_song().track_num
        1
        """
        self._song_idx = 0
        self._song_position = 0
        try:
            self._cur_song = self.songs[self._song_idx]
        except IndexError:
            self._cur_song = None

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
        >>> # When wrap is off, return None when album is finished
        >>> [a.next_song(wrap=False) for i in range(len(a.songs)+1)][-1]
        None
        """
        bumped = False
        if not self.songs:
            return None

        self._song_idx = self._song_idx + 1
        if self._song_idx >= len(self.songs):
            self._song_idx = 0
            if not wrap:
                self._song_idx -= 1
                bumped = True

        self._cur_song = self.songs[self._song_idx]
        if not bumped:
            self._song_position = 0
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
            self._song_position = 0
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

    def count_tracks(self):
        return(len(self.songs))

    def current_track_num(self):
        if self.cur_song() is not None:
            # TODO calculation is wrong, have to add all albums!
            return self.cur_song().track_num
        else:
            return 0


class Playlist(object):
    """
    Represents a playlist that is made up of one or more albums

    >>> Playlist(".").tag is None
    True
    >>> pl = Playlist("../audio/Bardic 012345678912")
    >>> len(pl.albums) # A single Album
    1
    """
    _playlists_by_tag = {}

    _playlists_by_id = {}

    @classmethod
    def get_playlist(cls, tag):
        """
        Fetches a playlist by its tag id and returns the
        respective Playlist() object.

        Returns None if the tag in not known

        >>> Playlist.get_playlist("012345678912").albums[0].name
        'The Roadsmell After The Rain'
        >>> Playlist.get_playlist("NOTTHERE") is None
        True
        """
        try:
            return cls._playlists_by_tag[tag]
        except KeyError:
            return None

    @classmethod
    def get_playlist_by_id(cls, id):
        """
        Fetches a playlist by its id and returns the
        respective Playlist() object.

        Returns None if the tag in not known
        """
        try:
            return cls._playlists_by_id[id]
        except KeyError:
            return None

    def __init__(self, path):
        self.path = path
        self.tag = None
        self._album_idx = None
        self._cur_album = None
        self._flag_repeat = False
        self.albums = []
        self.id = hashlib.sha256(path.encode('utf-8')).hexdigest()
        self._playlists_by_id[self.id] = self
        (_, self.name) = os.path.split(path)

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
                    info("Ignoring file {} in playlist {}, will only look for album directories here.".format(d, path))
                    continue

                album = Album(current)

                self.albums.append(album)

        # Remember all playlists by their tag
        if self.tag is not None:
            if self.tag in self._playlists_by_tag:
                raise Exception("tag "+self.tag+" found twice: " + path + ", " + str(self._playlists_by_tag[self.tag]))
            self._playlists_by_tag[self.tag] = self

        self.albums = sorted(self.albums, key=lambda x: x.name.lower())

        self._album_idx = 0
        # Try to remember which album was played last
        current_albums = [x.is_current_album for x in self.albums]
        if True in current_albums:
            self._album_idx = current_albums.index(current_album_dir)
    
        try:
            self._cur_album = self.albums[self._album_idx]
        except IndexError:
            self._cur_album = None

    def to_dict(self):
        return {
                "name": self.name,
                "id": self.id,
                "path": self.path,
                "current_album": self._album_idx,
                "albums": [ a.to_dict() for a in self.albums ]
                }
    def save_state(self, position=None):
        state = {"idx":self._album_idx, "repeat": self._flag_repeat}
        if position is not None:
            state['position'] = position

        if self._cur_album is not None:
            self._cur_album.save_state(position)

        with open(self.path+"/playlist.json", "w") as f:
            json.dump(state, f)

    def load_state(self):
        try:
            with open(self.path+"/playlist.json", "r") as f:
                state = json.load(f)
                self._album_idx = state["idx"]
                self._flag_repeat = state['repeat']
                try:
                    self._cur_album = self.albums[self._album_idx]
                except IndexError:
                    self._cur_album = None
        except FileNotFoundError:
            self.restart()
            return

        self._cur_album = self.albums[self._album_idx]
        self._cur_album.load_state()

    def restart(self):
        """
        Restarts a playlist from first track of first album.
        >>> pl = Playlist.get_playlist("012345678912")
        >>> _ = pl.next_song()
        >>> pl.restart()
        >>> pl.cur_song().track_num
        1
        >>> pl._album_idx
        0
        """
        self._album_idx = 0

        for album in self.albums:
            album.restart()

        if not self.albums:
            self._album_idx = None
            self._cur_album = None
        else:
            self._cur_album = self.albums[self._album_idx]

    def next_album(self, wrap=True):
        """
        Selects next album in playlist, does NOT restart it.

        >>> pl = Playlist.get_playlist("012345678912")
        >>> len(pl.albums)
        1
        >>> a = pl.next_album() # Wrap by default
        >>> a is None
        False
        >>> pl._album_idx
        0
        >>> a = pl.next_album(wrap=False) # If explicitly forbidden, do not wrap
        >>> a is None
        True
        """
        self._album_idx += 1
        if self._album_idx >= len(self.albums):
            if not (self._flag_repeat or wrap):
                return None
            self._album_idx -= 1

        self._cur_album = self.albums[self._album_idx]
        return self._cur_album

    def prev_album(self, wrap=True):
        """
        Selects previous album in playlist, does NOT restart it.

        >>> pl = Playlist.get_playlist("012345678912")
        >>> len(pl.albums)
        1
        >>> a = pl.prev_album() # Wrap by default
        >>> a is None
        False
        >>> pl._album_idx
        0
        >>> a = pl.prev_album(wrap=False) # If explicitly forbidden, do not wrap
        >>> a is None
        True
        """
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
            return self.cur_song()
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

    def cur_pos(self):
        if self._cur_album is None:
            return None

        return self._cur_album._song_position

    def count_songs(self):
        return sum([a.count_tracks() for a in self.albums])

    def current_song_index(self):
        track = 0
        for a in self.albums:
            if a is self._cur_album:
                break
            track += len(self.album.songs)

        if self._cur_album is not None:
            track += self._cur_album.current_track_num()
        return track

class Library(object):

    def __init__(self, audio_path):
        self.audio_path = audio_path

        self.playlists = []

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
                continue
                #raise Exception("not a directory: " + current)

            if d == "system":
                continue

            playlist = Playlist(current)
        self.playlists.append(playlist)

    def lookup_playlist(self, tag=None, id=None):
        if id is not None:
            return Playlist.get_playlist_by_id(id)
        else:
            return Playlist.get_playlist(tag)

if __name__ == "__main__":
    from SetupLogging import setup_stdout_logging
    from sys import argv

    getLogger('   Library').setLevel(DEBUG)

    #setup_stdout_logging()

    if len(argv) != 2:
        info("Error: Missing path argument.")
        exit(1)

    lib = Library(argv[1])
    #try:
    #    lib = Library(argv[1])
    #    input()
    #except Exception as e:
    #    debug("Error: " + repr(e))
    #    exit(1)

    info("Everything seems fine.")
