from setuptools import setup

setup(
    name='PlaylistCopy',
    version='0.2',
    author='Den',
    author_email='',
    py_modules=['playlistcopy'],
    entry_points={
        'console_scripts': ['playlistcopy = playlistcopy:main']
    },
    url='http://den.cx',
    license='LICENSE.txt',
    description='playlistcopy is a Python 3 program for merging and copying '
                '(and syncing) several tracks of several playlists '
                '(m3u/m3u8) to a destination device, even splitted in '
                'folders and shuffled.',
    long_description=open('README.rst').read(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Multimedia :: Sound/Audio :: Analysis',
        'Topic :: Multimedia :: Sound/Audio :: CD Audio :: CD Playing',
    ],
    install_requires=[
        'chardet',
        'hsaudiotag3k'
    ],
)