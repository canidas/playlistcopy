from setuptools import setup

setup(
    name='PlaylistCopy',
    version='1',
    author='Den',
    author_email='dev@den.cx',
    py_modules=['playlistcopy'],
    entry_points={
        'console_scripts': ['playlistcopy = playlistcopy:main']
    },
    url='http://den.cx',
    license='LICENSE.txt',
    description='playlistcopy is a Python 3 program for randmomized copying '
                'tracks playlist of (M3U/M3U8) to a destination device',
    long_description=open('README.rst').read(),
    classifiers=[
        'Environment :: Console',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 3',
        'Topic :: Multimedia :: Sound/Audio :: CD Audio :: CD Playing',
        'Topic :: Multimedia :: Sound/Audio :: Conversion',
    ],
    install_requires=[
        'chardet',
        'hsaudiotag3k'
    ],
)