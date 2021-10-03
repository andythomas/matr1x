import glob
import os

from setuptools import find_packages, setup

guipath = os.path.join('matr1x', 'control')
guifiles = set(glob.glob(os.path.join(guipath, '[!_]*.py'))) - \
    set([os.path.join(guipath, 'util.py')])
gui_scripts = ['sweep_generator=matr1x.scripts.sweep_generator:main [GUI]',
               'matrix_script=matr1x.scripts.matrix_script:main [GUI]']
for fn in guifiles:
    script_name = os.path.splitext(os.path.split(fn)[-1])[0]
    gui_scripts.append(
        f'{script_name}=matr1x.control.{script_name}:main [GUI]')


setup(
    name='matr1x',
    version='1.0',
    description='Python package for data acquisition and measurement control',
    url='https://github.com/andythomas/IFW_software',
    packages=find_packages(),
    python_requires='>3.6',
    install_requires=[
        'h5py',
        'numpy',
        'pymeasure',
        'pyserial',
        'pyvisa',
        'pyvisa-py',
        'urwid>2.0',
        'wrapt',
    ],
    extras_require={
        'SPI': ['spidev', 'RPi'],
        'GUI': ['pyqtgraph', 'PyQt5'],
    },
    entry_points={
        'gui_scripts': gui_scripts,
        'console_scripts': ['matrix=matr1x.scripts.matrix:main',
                            'matrix_gui=matr1x.scripts.matrix_gui:main',
                            ]
    },
)
