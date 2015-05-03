playlistcopy
============

playlistcopy is a Python 3 program for merging and copying (and syncing)
several tracks of several playlists (m3u/m3u8) to a destination device,
even splitted in folders and shuffled.

Per default playlistcopy rewrites file names to artist - album - track
(with help of `hsaudiotag3k <https://pypi.python.org/pypi/hsaudiotag3k>`_)
so it's important to have correct file tags. It also handles not unique
source tracks (if the same track is on several playlists). A track is
identified by its file name (rewritten one from tags or real filename
if disabled).

playlistcopy has two possible modes: *sync* and *append*. In *sync* mode
**playlistcopy removes all files which are not on the given playlists**!
In comparison to *sync*, *append* does not do any deletion.

Originally I wrote this script for my Kenwood car radio which only recognizes
255 tracks per folder (and 254 folders in total) on an USB-device. Nobody
wants to split thousands of tracks by hand…

Tasks
-----

sync, append
~~~~~~~~~~~~

Sync or append. See above.

::

    playlistcopy task [PARAMETERS] destination playlist [playlist ...]

===========================  ========================================================================
``--dry-run, -n``             Only make a trial run (No copying and deletion)
``--no-rewrite-filenames``    Don't rewrite filenames (No use of file tags)
``--shuffle``                 Shuffle tracks in destination (Only new tracks, for tracks-per-folder)
``--tracks-per-folder``       Maximum track count per folder (default 0, 0 = single folder)
``--folder-names``            Format for folder names (for tracks-per-folder, default: "Folder %d")
``destination``               Path to destination (e.g. usb storage)
``playlist [...]``            Path to playlist file; multiple playlists possible (M3U/M3U8)
===========================  ========================================================================

stats
~~~~~

Stats about tracks in destination. Currently only sums track count per artist
(including percentage).

::

    playlistcopy stats destination

Common Arguments
~~~~~~~~~~~~~~~~

======================  ==================================================================
``--help, -h``           Print help and exit
``--verbose, -v``        Show output for all actions of tracks (follows after task!)
``--version, -V``        Print version and exit
======================  ==================================================================

Dependencies
------------

* Python 3.1 (at least)
* hsaudiotag3k (semi-optional)
* chardet (optional)

License
-------

playlistcopy is licensed under the terms of GPLv3+.
