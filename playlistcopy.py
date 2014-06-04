""" playlistcopy is a Python 3 program for randmomized copying tracks
playlist of (M3U/M3U8) to a destination device.

See readme.rst for more information.

Dependencies:
    * Python 3.1 (at least)
    * hsaudiotag3k
    * chardet (optional)

License: GPLv3+
"""

import argparse
import codecs
import collections
import os
import logging
import multiprocessing as mp
import multiprocessing.sharedctypes
import shutil
import subprocess
import random
import re
import tempfile

try:
    import chardet
except ImportError:
    chardet = None

from hsaudiotag import auto  # hsaudiotag3k


class PlaylistCopy:
    """ Class for reading multiple playlists (M3U-format) and
    """
    _file_types = ('mp3', 'm4a', 'wav')  # Supported by Kenwood
    _folder_name = 'Folder %d'  # %d is count

    def __init__(self, dst_dir, playlists, lame_bin=None, tracks_per_dir=0,
                 randomize_tracks=True, convert_jobs=1, move_jobs=1, quiet=False):
        """ Constructor

        :param dst_dir: Destination directory
        :param playlists: List of path to playlist paths
        :param lame_bin: Path to LAME binary
        :param tracks_per_dir: Maximum tracks per directory. 0 disables splitting.
        :param randomize_tracks: Randomize tracks? Only useful for tracks_per_dir.
        :param convert_jobs: Process count for converting jobs
        :param move_jobs: Process count for moving jobs
        :param quiet: Suppress print()-output
        """
        self._dst_dir = dst_dir
        self._playlists = playlists
        self._lame_bin = lame_bin
        self._tracks_per_dir = tracks_per_dir
        self._randomize_tracks = randomize_tracks
        self._convert_jobs_count = convert_jobs
        self._move_job_count = move_jobs
        self._quiet = quiet

        self._tmp_dir = tempfile.mkdtemp()
        self._logger = mp.get_logger()
        self._playlist_tracks = set()
        self._sync_tracks = collections.OrderedDict()
        self._dst_tracks = set()  # lowered values
        self._dst_dir_dirs = collections.OrderedDict()

        if lame_bin is not None and not os.path.isfile(self._lame_bin):
            raise FileNotFoundError('lame executable not found')

    def run(self):
        """ Run processes
        """
        self._get_files_of_dst()

        logging.info('Parsing %d playlists' % len(self._playlists))

        for pl in self._playlists:
            self._parse_playlist(pl)

        if not self._quiet:
            print('Playlists contain %d new items' % len(self._sync_tracks))

        if len(self._sync_tracks) > 0:
            self._determine_dst_locations()
            self._start_jobs()

        # Clean-up
        try:
            shutil.rmtree(self._tmp_dir)
        except PermissionError:
            # It's possible that _move_job and rmtree try to delete the same file
            pass

        if not self._quiet:
            print('Finished')

    def _start_jobs(self):
        """ Start all worker processes and wait for finish

        TODO: Rewrite entire process communication. copy_queue.join() deadlocks
        when processing many tracks. But without this join, the last could be
        skipped while copying because the parent process terminates the copy
        worker. The current deadlock is the better approch because all files
        will still be copied and only the empty temporary directory won't be
        deleted.
        """
        # Queues for mp
        convert_queue = mp.JoinableQueue()
        copy_queue = mp.JoinableQueue()
        for track in self._sync_tracks.values():
            convert_queue.put(track)

        todo_tracks = convert_queue.qsize()
        done_tracks = mp.sharedctypes.Value('d', 0)

        # Start converter processes
        for i in range(self._convert_jobs_count):
            p = mp.Process(target=_convert_job, name='ConvProcess-%d' % i,
                           args=(convert_queue, copy_queue, self._tmp_dir, self._lame_bin))
            p.daemon = True
            p.start()

        # Start move processes
        for i in range(self._move_job_count):
            p = mp.Process(target=_move_job, name='MoveProcess-%d' % i,
                           args=(copy_queue, todo_tracks, done_tracks, self._quiet))
            p.daemon = True
            p.start()

        # Wait for all workers to finish
        convert_queue.join()
        copy_queue.join()  # Deadlock if there are many tracks

    def _get_files_of_dst(self):
        """ Build list of all tracks of destination
        """
        def add_file(file, directory_number):
            self._dst_tracks.add(file.lower())  # lowering is important
            self._dst_dir_dirs[directory_number].add(file)

        for f in os.listdir(self._dst_dir):
            path = os.path.join(self._dst_dir, f)

            # Don't iterate through sub directories when no folders are used
            if self._tracks_per_dir == 0:
                self._dst_dir_dirs[1] = set()
                add_file(f, 1)
            else:
                # Ignore files in destination root directory
                if not os.path.isdir(path):
                    continue

                # Extract directory number
                try:
                    folder_name_format = self._folder_name.replace('%d', r'(\d+)')
                    number = int(re.findall(r'^%s$' % folder_name_format, f)[0])
                except IndexError:
                    continue  # Folder name doesn't match format

                self._dst_dir_dirs[number] = set()

                # Iterate through sub directories
                for f2 in os.listdir(path):
                    path2 = os.path.join(self._dst_dir, f, f2)
                    if not os.path.isfile(path2):
                        continue  # Ignore sub sub directories
                    add_file(f2, number)

    def _parse_playlist(self, pl):
        """ Build initial list of files (read playlists)
        """
        pl_path = os.path.dirname(os.path.realpath(pl))
        pl_name = os.path.splitext(os.path.basename(pl))[0]

        # Deal with file encoding, BOM
        encoding = None
        raw = open(pl, 'rb').read(min(32, os.path.getsize(pl)))
        if raw.startswith(codecs.BOM_UTF8):
            encoding = 'utf-8-sig'
        elif chardet is not None:
            result = chardet.detect(raw)
            encoding = result['encoding']

        with open(pl, 'r', encoding=encoding) as f:
            for line in f:
                if line.startswith('#'):
                    continue  # Ignore M3U directives

                src_path = os.path.join(pl_path, line.replace('\n', ''))

                # Some hard checks
                if not os.path.isfile(src_path):
                    raise FileNotFoundError('File "%s" does not exists!' % src_path)
                if not src_path.endswith(self._file_types):
                    raise IOError('File "%s" is not in %s!' % (src_path, self._file_types))

                # Generate new filename
                tags = auto.File(src_path)
                dst_name = '%s - %s (%s)' % (tags.artist, tags.title, pl_name)
                dst_name = re.sub('[^\w\s()-\.\']', '', dst_name).strip()
                ext = os.path.splitext(src_path)[-1]
                dst_name_ext = ''

                # Check if file with same potential filename already exists in same PL
                # If so, append (1), (2), etc. to filename
                nth_file = 0
                while True:
                    nth_file += 1
                    nth = ' (%d)' % nth_file if nth_file > 1 else ''
                    dst_name_ext = '%s%s%s' % (dst_name, nth, ext)

                    if dst_name_ext not in self._playlist_tracks:
                        break

                # It's important to always have a list of all tracks of all playlists
                # That's important for correct working of the above check
                self._playlist_tracks.add(dst_name_ext)

                # Skip file if file with filename already exists on destination
                # Lowering is important for tracks with same artist and title
                #   on same playlist because of ordering problems
                # Example: Same artist, same title, different album,
                #   some letter lowercase instead of uppercase
                if dst_name_ext.lower() in self._dst_tracks:
                    self._logger.info('Skipping file (already exists) %s' % dst_name_ext)
                else:
                    self._sync_tracks[dst_name_ext] = [dst_name_ext, src_path, '']

    def _determine_dst_locations(self):
        """ Determine where to place which track
        """
        # Randomize tracks (only if dirs are being created)
        tracks = list(self._sync_tracks.keys())
        if self._randomize_tracks and self._tracks_per_dir != 0:
            random.shuffle(tracks)

        i = 0
        while True:
        #for i in range(1, 255):  # 254 = max. folder count (255 is /)
            i += 1

            if len(tracks) == 0:
                break  # No tracks left, so break

            folder_name = self._folder_name % i
            folder_path = os.path.join(self._dst_dir, folder_name)

            # Track count per directory check
            if self._tracks_per_dir != 0:
                # If folder already exists, check file count
                if i in self._dst_dir_dirs:
                    tracks_in_dir = len(self._dst_dir_dirs[i])
                    if tracks_in_dir >= self._tracks_per_dir:
                        continue  # Skip this full directory
                    else:
                        remainder = self._tracks_per_dir - tracks_in_dir
                else:
                    # Create new directory
                    os.mkdir(folder_path)
                    remainder = self._tracks_per_dir
            else:
                remainder = len(tracks)  # Remainer is as high as track count
                folder_path = self._dst_dir  # No directory must be created

            # Allocate track to destination directory
            for j in range(remainder):
                try:
                    track = tracks.pop(0)
                    self._sync_tracks[track][2] = os.path.join(folder_path, track)
                except IndexError:
                    break  # No more tracks left


def _convert_job(convert_queue, copy_queue, tmp_dir, lame_bin=None):
    """ Subprocess worker to downconvert file
    """
    logger = mp.get_logger()
    while True:
        item = convert_queue.get()
        temp_path = os.path.join(tmp_dir, item[0])
        converted = False

        if lame_bin is not None:
            if item[0].endswith('mp3'):
                lame_params = [lame_bin, '-b 128', '--silent', item[1], temp_path]
                logger.info('Execute lame %s' % lame_params)
                subprocess.call(lame_params)
                logger.info('Finished executing lame %s' % lame_params)
                converted = True

        if not converted:
            # TODO Don't copy, just rename
            logger.info('No converting for %s' % item[0])
            shutil.copyfile(item[1], temp_path)

        copy_queue.put((temp_path, item[2]))
        convert_queue.task_done()


def _move_job(copy_queue, todo_tracks, done_tracks, quiet=False):
    """ Subprocess worker to move a file to destination
    """
    logger = mp.get_logger()
    while True:
        item = copy_queue.get()
        logger.info('Copy file %s to %s' % (item[0], item[1]))

        if os.path.isfile(item[0]):
            # TODO: On OSError-exception, kill everything
            # Use copyfile instead of move because move fails sometimes
            shutil.copyfile(item[0], item[1])
            logger.info('Finished copying of file %s' % item[0])
            os.unlink(item[0])  # There is rmtree, but do this anyway
        else:
            # Something has happened to tmp dir?
            logger.error('Skipped copying of file (missing file) %s' % item[0])

        if not quiet:
            with done_tracks.get_lock():
                done_tracks.value += 1
                f = (done_tracks.value, todo_tracks,
                     done_tracks.value / todo_tracks * 100)
                print('Finished track %d/%d (%.2f%%)' % f)

        copy_queue.task_done()


def main():
    """ Argument parser for command line support
    """
    description = 'Script for copying playlist tracks (M3U/M3U8) to a destination device'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--convert-workers', default=1, type=int,
                        help='jobs for converting tracks down (default 1)')
    parser.add_argument('--lame',
                        help='path to LAME binary to down convert tracks (128 kbps)')
    parser.add_argument('--move-workers', default=1, type=int,
                        help='jobs for moving files (default 1)')
    parser.add_argument('--no-randomize', action='store_true',
                        help='don\'t copy tracks randomized to destination')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='suppress normal output')
    parser.add_argument('--tracks-per-dir', default=0, type=int,
                        help='maximum track count per directory (default 0, 0 = single folder)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show output for all track actions')
    parser.add_argument('-V', '--version', action='version', version='%(prog)s 0.1',
                        help='print version and exit')

    parser.add_argument('destination',
                        help='path to destination (e.g. usb storage)')
    parser.add_argument('playlists', metavar='playlist', nargs='+',
                        help='path to playlist files, multiple playlists possible (M3U/M3U8)')

    args = parser.parse_args()

    if args.verbose:
        mp.log_to_stderr()
        logger = mp.get_logger()
        logger.setLevel(logging.INFO)

    pc = PlaylistCopy(dst_dir=args.destination, playlists=args.playlists,
                      lame_bin=args.lame, tracks_per_dir=args.tracks_per_dir,
                      randomize_tracks=not args.no_randomize,
                      convert_jobs=args.convert_workers,move_jobs=args.move_workers,
                      quiet=args.quiet)
    pc.run()


if __name__ == '__main__':
    main()
