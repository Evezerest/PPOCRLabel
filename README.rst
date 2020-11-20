PPOCRLabel
===========

PPOCRLabel is a graphical semi-automatic image annotation tool.

It is written in Python and uses Qt for its graphical interface.

Annotations are saved as PPOCR format in a txt file



`Watch a demo video <>`

Installation
------------------


Build from source
~~~~~~~~~~~~~~~~~

Linux/Ubuntu/Mac requires `Python
3 or above <https://www.python.org/getit/>`__ and  `PyQt5 <https://pypi.org/project/PyQt5/>`__ are strongly recommended.


Windows + Anaconda
^^^^^^^^^^^^^^^^^^

Download and install `Anaconda <https://www.anaconda.com/download/#download>`__ (Python 3+)

Open the Anaconda Prompt and go to the `labelImg <#labelimg>`__ directory

.. code:: shell

    conda install pyqt=5
    pyrcc5 -o libs/resources.py resources.qrc
    python PPOCRLabel.py


Ubuntu Linux
^^^^^^^^^^^^

Python 3 + Qt5

.. code:: shell

    sudo apt-get install pyqt5-dev-tools
    sudo pip3 install -r requirements/requirements-linux-python3.txt
    make qt5py3
    python3 PPOCRLabel.py

macOS
^^^^^
Python 3 + Qt5 

.. code:: shell

    brew install qt  # Install qt-5.x.x by Homebrew

    or using pip

    pip3 install pyqt5

    make qt5py3
    python3 PPOCRLabel.py



Usage
-----

Steps
~~~~~~~~~~

1. Build and launch using the instructions above.
2. Click 'Open Dir' in Menu/File
3. Click 'Auto recognition', use PPOCR model to automatically annotate images which marked with 'X' before the file name. 
4. Creat Box:
    4.1 Click 'Create RectBox' or press 'W' in English keyboard mode to draw a new rectangle detection box. Click and release left mouse to select a region to annotate the rect box.
    
    4.2 Press 'P' to enter four-point labeling mode which enables you to creat any four-point shape by clicking four points with the left mouse button in succession and DOUBLE CLICK the left mouse as the signal of labeling completion.
    
5. Click 're-Recognition', model will rewrite ALL recognition results in ALL detection box.
6. Double click the result in 'recognition result' list to manually change inaccurate recognition results.
7. Click 'Save' to save the annotation of this image.

Note:
~~~~~~~
- The annotation will be saved to the folder as same as the picture path you opened. 'label.txt' stores the labels you manually confirmed.

- If you manually enter the recognition result after drawing the box, the result will be overwritten after clicking re-Recognition by the model.


Hotkeys
~~~~~~~

+------------+--------------------------------------------+
| p          | Create a fout-point box                    |
+------------+--------------------------------------------+
| w          | Create a rect box                          |
+------------+--------------------------------------------+
| d          | Next image                                 |
+------------+--------------------------------------------+
| a          | Previous image                             |
+------------+--------------------------------------------+
| del        | Delete the selected rect box               |
+------------+--------------------------------------------+
| Ctrl + s   | Save                                       |
+------------+--------------------------------------------+
| Ctrl++     | Zoom in                                    |
+------------+--------------------------------------------+
| Ctrl--     | Zoom out                                   |
+------------+--------------------------------------------+
| ↑→↓←       | Keyboard arrows to move selected rect box  |
+------------+--------------------------------------------+


How to reset the settings
~~~~~~~~~~~~~~~~~~~~~~~~~

In case there are issues with loading the classes, you can either:

1. From the top menu of the labelimg click on Menu/File/Reset All
2. Remove the `.labelImgSettings.pkl` from your home directory. In Linux and Mac you can do:
    `rm ~/.labelImgSettings.pkl`


How to contribute
~~~~~~~~~~~~~~~~~

Send a pull request

License
~~~~~~~
`Free software: MIT license <https://github.com/tzutalin/labelImg/blob/master/LICENSE>`_


Related
~~~~~~~

1. `ImageNet Utils <https://github.com/tzutalin/ImageNet_Utils>`__ to
   download image, create a label text for machine learning, etc
2. `Use Docker to run labelImg <https://hub.docker.com/r/tzutalin/py2qt4>`__
3. `Generating the PASCAL VOC TFRecord files <https://github.com/tensorflow/models/blob/4f32535fe7040bb1e429ad0e3c948a492a89482d/research/object_detection/g3doc/preparing_inputs.md#generating-the-pascal-voc-tfrecord-files>`__
4. `App Icon based on Icon by Nick Roach (GPL) <https://www.elegantthemes.com/>`__
5. `Setup python development in vscode <https://tzutalin.blogspot.com/2019/04/set-up-visual-studio-code-for-python-in.html>`__
6. `The link of this project on iHub platform <https://code.ihub.org.cn/projects/260/repository/labelImg>`__
7. `Tzutalin. LabelImg. Git code (2015). <https://github.com/tzutalin/labelImg>`__

