playlistcopy
------------

playlistcopy is a Python 3 program for randmomized copying tracks
playlist of (M3U/M3U8) to a destination device.

playlistcopy creates new file names for the tracks from artist name and track
title of ID3 tags (with help of
`hsaudiotag3k <https://pypi.python.org/pypi/hsaudiotag3k>`_). So it's
important to have maintained ID3 tags!

playlistcopy can also down convert MP3 tracks (with help of
`LAME <http://lame.sourceforge.net/>`_ and can split tracks to single
directories with a maximum track count per directory. It has the ability to
execute this conversion and copying with help of multiprocessing for better
speed. This number of processes is adjustable.

The script has *some* sync functionality: It adds missing directories (count)
and places new tracks in not full directories. It skips tracks with same
artist and same title of same playlist (but recognizes multiple tracks of
same artist and same title on same playlist). But this sync breaks the
concept of implemented randomness. Currently it doesn't delete tracks being
on, destination but not on playlist. It also doesn't move tracks on
destination which would keep some kind of balance (see next section).

Originally I wrote this script for my Kenwood car radio which only can
recognize 255 tracks per directory (and 254 direcotires in total) on an
USB-device. Regarding the copy slowness of USB 2 devices I implemented
multiprocessing. The placement of tracks is randomized because the random
alogrithm of Kenwood devices seem to only randomize files but not directories.
I made some things optional in the hope that somebody could use it for
other features playlistcopy has also built in.

License
=======

playlistcopy is licensed under the terms of GPLv3+.

Dependencies
============

* Python 3.1 (at least)
* hsaudiotag3k
* chardet (optional)

Usage
=====
::

    playlistcopy [PARAMETERS] destination playlist [playlist ...]

Parameters
==========

======================  ==================================================================
``--help, -h``           Print help and exit
``--convert-workers``    Jobs for converting tracks down (default 1)
``--lame``               Path to LAME binary to down convert tracks (128 kbps)
``--move-workers``       Jobs for moving files (default 1)
``--no-randomize``       Don't copy tracks randomized to destination
``--quiet, -q``          Suppress normal output
``--tracks-per-dir``     Maximum track count per directory (default 0, 0 = single folder)
``--verbose, -v``        Show output for all actions of tracks
``--version, -V``        Print version and exit
``destination``          Path to destination (e.g. usb storage)
``playlist [...]``       Path to playlist file, multiple playlists possible (M3U/M3U8)
======================  ==================================================================
