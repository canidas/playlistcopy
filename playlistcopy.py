#!/usr/bin/env python3

import argparse
import collections
import logging
import os
import random
import re
import shutil

try:
    import chardet
except ImportError:
    chardet = None


class PlaylistCopy:
    """ playlistcopy is a Python 3 program for merging and copying (and
    syncing) several tracks of several playlists (m3u/m3u8) to a destination
    device, even splitted in folders and shuffled.

    Dependencies:
        * Python 3.1 (at least)
        * hsaudiotag3k (semi-optional)
        * chardet (optional)

    Licence:
        GPLv3+
    """
    def __init__(self, destination, playlists, mode='sync', rewrite_file_names=True, tracks_per_folder=0,
                 shuffle=False, folder_name='Folder %d', verbose=False, dry_run=False):
        self.destination = destination
        self.playlists = playlists
        self.mode = mode
        self.rewrite_file_names = rewrite_file_names
        self.tracks_per_folder = tracks_per_folder
        self.shuffle = shuffle
        self.folder_name = folder_name
        self.dry_run = dry_run

        self.playlists_files = []
        self.playlists_files_rewritten = collections.OrderedDict()  # New name -> fs path
        self.destination_files = []
        self.destination_folders = collections.OrderedDict()  # Number of files per folder

        self.logger = logging.Logger(__name__)
        level = logging.WARNING if not verbose else logging.DEBUG
        console = logging.StreamHandler()
        console.setLevel(level)
        self.logger.addHandler(console)
        self.logger.setLevel(level)

    def run(self):
        """ Start process
        """
        for playlist_file in self.playlists:
            self._parse_playlist(playlist_file)

        self._build_rewritten_filenames()
        self._build_destination_file_list()

        self._sync()

    def _parse_playlist(self, file):
        """ Parse a M3U playlist
        """
        file_dir = os.path.dirname(os.path.realpath(file))

        # Deal with file encoding
        encoding = None
        if chardet is not None:
            result = chardet.detect(open(file, 'rb').read())
            encoding = result['encoding']

        with open(file, 'r', encoding=encoding) as f:
            for line in f:
                if line.startswith('#'):
                    continue  # Ignore M3U directives
                full_path = os.path.join(file_dir, line.rstrip())
                if not os.path.isfile(full_path):
                    self.logger.warning('File doesn\'t exist and is skipped: %s' % full_path)
                else:
                    self.playlists_files.append(full_path)

    def _build_destination_file_list(self):
        """ Build list of all files of destination folder
        """
        for f in os.listdir(self.destination):
            path = os.path.join(self.destination, f)

            # Don't iterate through sub directories when no folders are used
            if self.tracks_per_folder == 0:
                if os.path.isfile(path):
                    self.destination_files.append(path)
            else:
                # Check if folder name matchs folder name format
                folder_number = self._extract_folder_number(f)
                if folder_number is None:
                    continue  # Folder name doesn't match format

                self.destination_folders[folder_number] = 0
                for f2 in os.listdir(path):
                    path2 = os.path.join(self.destination, f, f2)
                    if os.path.isfile(path2):  # Ignore sub sub directories
                        self.destination_files.append(path2)
                        self.destination_folders[folder_number] += 1

    def _build_rewritten_filenames(self):
        """ Rewrite file names of playlists for destination folder
        """
        for k, f in enumerate(self.playlists_files):
            name, ext = os.path.splitext(os.path.basename(f))

            # Rewrite file names to ID3 tags
            # TODO Maximum filename length on some file systems
            if self.rewrite_file_names:
                from hsaudiotag import auto  # hsaudiotag3k
                tags = auto.File(f)
                if not tags.artist.strip():
                    raise IOError('Tag artist is empty %s' % f)
                if not tags.album.strip():
                    raise IOError('Tag album is empty %s' % f)
                if not tags.title.strip():
                    raise IOError('Tag title is empty %s' % f)
                name = '%s - %s - %s' % (tags.artist, tags.album, tags.title)  # Actually - should be –
                name = re.sub('[^\w\s()-\.\']', '', name).strip()

            # Check if file with same potential filename already exists in same PL
            # If so, append (1), (2), etc. to filename
            nth_file = 0
            while True:
                nth_file += 1
                nth = ' (%d)' % nth_file if nth_file > 1 else ''
                new_name = '%s%s' % (name, nth)
                # Compare lowered names, needed for case-insensitive file systems
                rewritten_lower = map(lambda n: n.lower(), self.playlists_files_rewritten.values())
                if (new_name + ext).lower() not in rewritten_lower:
                    name = new_name
                    break

            self.playlists_files_rewritten[k] = name + ext

    def _compare(self):
        """ Determine which tracks become added and which tracks become removed
        """
        # Filenames for comparison (lowered names needed for case-insensitive file systems)
        pl_filenames = [name.lower() for name in self.playlists_files_rewritten.values()]
        dst_filenames = [os.path.basename(f).lower() for f in self.destination_files]

        # Some assertions
        if len(self.playlists_files) != len(set(self.playlists_files_rewritten)):
            raise AssertionError('Playlist files don\'t contain unique filenames only (error in file renaming?)')
        if len(dst_filenames) != len(set(dst_filenames)):
            raise AssertionError('Destination files don\'t contain unique filenames only (across all folders)')

        # Compare: New files and files to delete (only compare filenames)
        additions = collections.OrderedDict()
        deletions = {}
        for k, name in enumerate(pl_filenames):
            if name not in dst_filenames:
                additions[k] = self.playlists_files[k]
        for k, dst_file in enumerate(dst_filenames):
            if dst_file not in pl_filenames:
                deletions[k] = self.destination_files[k]

        return additions, deletions

    def _sync(self):
        """ Sync: Get additions and deletions, shuffling, execute sync
        """
        self.logger.warning('All playlists have %d tracks' % len(self.playlists_files))

        additions, deletions = self._compare()

        if self.mode == 'sync':
            info_deletions = '%d deletions' % len(deletions)
        else:
            info_deletions = '0 deletions (disabled)'
        self.logger.warning('%d additions, %s' % (len(additions), info_deletions))

        if self.dry_run:
            self.logger.warning('PERFORMING DRY RUN')

        # In sync mode: delete files not matched
        if self.mode == 'sync':
            self._sync_deletions(deletions)

        if self.shuffle:  # Shuffle works only for new tracks here
            keys = list(additions)
            random.shuffle(keys)
            for k in keys:
                additions.move_to_end(k)

        self._sync_additions(additions)

    def _sync_additions(self, additions):
        """ Sync additions: Create needed folders and copy files
        """
        folder_mapping = self._prepare_copying_additions(additions)

        tracks_done = 0
        for k, f in additions.items():
            tracks_done += 1
            dst_path = os.path.join(folder_mapping[k], self.playlists_files_rewritten[k])
            percent = tracks_done / len(additions) * 100
            self.logger.info('Copying file %s -> %s (%.2f%%)' % (f, dst_path, percent))
            if not self.dry_run:
                shutil.copyfile(f, dst_path)

    def _prepare_copying_additions(self, additions):
        """ Prepare copying: Create folders and allocate files to folders
        """
        mapping = {}
        tracks_stack = additions.copy()
        folder_count = 0

        while True:
            folder_count += 1

            if len(tracks_stack) == 0:
                break

            if self.tracks_per_folder != 0:
                folder_path = os.path.join(self.destination, self.folder_name % folder_count)

                # Create needed folder which currently does not exist
                if folder_count not in self.destination_folders:
                    self.logger.info('Creating folder "%s"' % folder_path)
                    if not self.dry_run:
                        os.mkdir(folder_path)

                    self.destination_folders[folder_count] = 0
                    remainder = self.tracks_per_folder
                else:
                    tracks_in_folder = self.destination_folders[folder_count]
                    if tracks_in_folder >= self.tracks_per_folder:
                        continue  # Skip full folder
                    else:
                        remainder = self.tracks_per_folder - tracks_in_folder
            else:
                remainder = len(tracks_stack)  # Remainer is as high as track count
                folder_path = self.destination  # No directory must be created

            # Allocate tracks to folder
            for i in range(remainder):
                try:
                    track = tracks_stack.popitem(False)
                    mapping[track[0]] = folder_path
                    if self.tracks_per_folder != 0:
                        self.destination_folders[folder_count] += 1
                except KeyError:
                    break  # No more tracks left

        return mapping

    def _sync_deletions(self, deletions):
        """ Sync deletions: Delete files and delete empty folders
        """
        for k, f in deletions.items():
            self.logger.info('Deleting file %s' % f)
            if not self.dry_run:
                os.unlink(f)

            # Keep file and folder lists in sync
            self.destination_files.remove(f)
            if self.tracks_per_folder != 0:
                folder_name = os.path.basename(os.path.dirname(f))
                folder_number = self._extract_folder_number(folder_name)
                self.destination_folders[folder_number] -= 1

        # Delete empty folders
        if self.tracks_per_folder != 0:
            for folder_number, file_count in self.destination_folders.items():
                if file_count == 0:
                    folder_path = os.path.join(self.destination, self.folder_name % folder_number)
                    if not self.dry_run:
                        os.rmdir(folder_path)
                    del self.destination_folders[folder_number]
                    self.logger.info('Deleting folder %s' % folder_path)

    def _extract_folder_number(self, folder):
        """ Extract folder number from name
        """
        try:
            folder_name_format = self.folder_name.replace('%d', r'(\d+)')
            return int(re.findall(r'^%s$' % folder_name_format, folder)[0])
        except IndexError:
            return None  # Folder name doesn't match format


class PlaylistCopyStats():
    """ Build stats for tracks in destination
    """
    def __init__(self, destination):
        self.destination = destination
        self.tracks = {}

    def _get_tracks(self):
        """ Walk through all files and folders
        """
        from hsaudiotag import auto  # hsaudiotag3k
        for root, dirs, files in os.walk(self.destination):
            for file in files:
                path = os.path.join(root, file)
                tags = auto.File(path)
                if not tags.valid:
                    print(path)
                    continue

                artist = tags.artist.strip()
                if not artist:
                    artist = 'Unknown artist'
                album = tags.album.strip()
                if not album:
                    album = '_'
                title = tags.title.strip()
                if not title:
                    title = 'Unknown track'

                if artist not in self.tracks:
                    self.tracks[artist] = {}
                if album not in self.tracks[artist]:
                    self.tracks[artist][album] = []

                self.tracks[artist][album].append(title)

    def group_by_artist(self):
        """ Sum by artists
        """
        artist_track_count = {}
        track_count = 0
        for artist, albums in self.tracks.items():
            for album, tracks in albums.items():
                if artist not in artist_track_count:
                    artist_track_count[artist] = 0
                artist_track_count[artist] += len(tracks)
                track_count += len(tracks)
        return track_count, artist_track_count

    def print_stats(self):
        """ Print stats (console)
        """
        self._get_tracks()
        track_count, artist_track_count = self.group_by_artist()
        print('Tracks in total: %d\n' % track_count)

        keys = list(artist_track_count.keys())
        keys.sort()
        for k in keys:
            percent = artist_track_count[k] / track_count * 100
            print('%s: %s (%.2f%%)' % (k, artist_track_count[k], percent))


class ArgumentParser():
    def __init__(self):
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument('-V', '--version', action='version', version='%(prog)s 0.2',
                                 help='print version and exit')

        self.subparsers = self.parser.add_subparsers(dest='task')
        self._add_parser('sync')
        self._add_parser('append')
        #self._add_parser('reshuffle')
        self._add_parser('stats')

    def parse_args(self):
        args = self.parser.parse_args()
        if args.task in ('sync', 'append'):
            plc = PlaylistCopy(args.destination, args.playlists, args.task,
                               rewrite_file_names=not args.no_rewrite_filenames,
                               tracks_per_folder=args.tracks_per_folder, shuffle=args.shuffle,
                               folder_name=args.folder_names, verbose=args.verbose,
                               dry_run=args.dry_run)
            plc.run()
        elif args.task == 'stats':
            plcs = PlaylistCopyStats(args.destination)
            plcs.print_stats()
        if args.task is None:
            self.parser.print_help()

    def _add_parser(self, name):
        parser = self.subparsers.add_parser(name)
        parser.add_argument('destination', help='path to destination (e.g. usb storage)')
        if name in ('sync', 'append'):
            parser.add_argument('--dry-run', '-n', action='store_true',
                                help='only make a trial run (no copying and deletion)')
            parser.add_argument('--no-rewrite-filenames', action='store_true',
                                help='don\'t rewrite filenames (no use of file tags)')
            parser.add_argument('--shuffle', action='store_true',
                                help='shuffle tracks in destination (only new tracks, for tracks-per-folder)')
            #parser.add_argument('--reshuffle', action='store_true', help='reshuffle all tracks in destination')
            parser.add_argument('--tracks-per-folder', default=0, type=int,
                                help='maximum track count per folder (default 0, 0 = single folder)')
            parser.add_argument('playlists', metavar='playlist', nargs='+',
                                help='path to playlist files, multiple playlists possible (m3u)')
        parser.add_argument('--folder-names', default='Folder %d',
                            help='format for folder names (for tracks-per-folder, default: "%(default)s")')
        parser.add_argument('-v', '--verbose', action='store_true',
                            help='show output for all track actions')


def main():
    parser = ArgumentParser()
    parser.parse_args()


if __name__ == '__main__':
    main()
