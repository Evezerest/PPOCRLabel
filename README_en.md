# PPOCRLabel

PPOCRLabel is a semi-automatic graphic annotation tool suitable for OCR field. It is written in python3 and pyqt5. Annotations can be directly used for the training of PPOCR detection and recognition models.

## Installation

**需要首先安装paddleOCR或将项目文件放置在paddleOCR目录下**

### Windows + Anaconda

Download and install [Anaconda](https://www.anaconda.com/download/#download) (Python 3+)

Open the Anaconda Prompt and go to the PPOCRLabel directory

```
conda install pyqt=5
pyrcc5 -o libs/resources.py resources.qrc
python PPOCRLabel.py
```

### Ubuntu Linux

```
sudo apt-get install pyqt5-dev-tools
sudo apt-get install trash-cli
sudo pip3 install -r requirements/requirements-linux-python3.txt
make qt5py3
python3 PPOCRLabel.py
```

### macOS
Python 3 + Qt5
```
brew install qt  # Install qt-5.x.x by Homebrew

# or using pip

pip3 install pyqt5

make qt5py3
python3 PPOCRLabel.py
```
Python 3 Virtualenv (Recommended)

Virtualenv can avoid a lot of the QT / Python version issues
```
brew install python3
pip3 install pipenv
pipenv run pip install pyqt5==5.12.1 lxml
pipenv run make qt5py3
python3 PPOCRLabel.py
[Optional] rm -rf build dist; python setup.py py2app -A;mv "dist/labelImg.app" /Applications
```
## Usage

### Steps

1. Build and launch using the instructions above.

2. Click 'Open Dir' in Menu/File

3. Click 'Auto recognition', use PPOCR model to automatically annotate images which marked with 'X' before the file name.

4. Create Box:

   4.1 Click 'Create RectBox' or press 'W' in English keyboard mode to draw a new rectangle detection box. Click and release left mouse to select a region to annotate the rect box.

   4.2 Press 'P' to enter four-point labeling mode which enables you to create any four-point shape by clicking four points with the left mouse button in succession and DOUBLE CLICK the left mouse as the signal of labeling completion.

5. Click 're-Recognition', model will rewrite ALL recognition results in ALL detection box.

6. Double click the result in 'recognition result' list to manually change inaccurate recognition results.

7. Click 'Save' to save the annotation of this image.

1. 使用上述命令安装与运行程序。
2. 在菜单栏点击 “文件” - "打开目录" 选择待标记图片的文件夹。
3. 点击 ”自动标注“，使用PPOCR超轻量模型对图片文件名前图片状态为 “X” 的图片进行自动标注。
4. 点击 “矩形标注”（或在英文模式下点击键盘中的 “W”)，用户可对当前图片中模型未检出的部分进行手动绘制标记框。点击键盘P，则使用四点标注模式（或点击“编辑” - “四点标注”），用户依次点击4个点后，双击左键表示标注完成。
5. 标记框绘制完成后，用户点击 “确认”，检测框会先被预分配一个 “待识别” 标签。
6. 将图片中的所有检测画绘制/调整完成后，点击 “重新识别”，PPOCR模型会对当前图片中的**所有检测框**重新识别。
7. 双击识别结果，对不准确的识别结果进行手动更改。
8. 点击 “保存”，图片状态切换为 “√”，跳转至下一张。
9. 点击 “删除图像”，图片将会被删除至回收站。
10. 关闭应用程序或切换文件路径后，手动保存过的标签将会被存放在所打开图片文件夹下的*Label.txt*中。在菜单栏点击 “PaddleOCR” - "保存识别结果"后，会将此类图片的识别训练数据保存在*crop_img*文件夹下，识别标签保存在*rec_gt.txt*中。

### Note

1. PPOCRLabel产生的文件包括一下几种，请勿手动更改其中内容，否则会引起程序出现异常。

   |    文件名     |                             说明                             |
   | :-----------: | :----------------------------------------------------------: |
   |   Label.txt   | 检测标签。可直接用于PPOCR检测模型训练。用户每保存10张检测结果后，程序会进行自动写入。当用户关闭应用程序或切换文件路径后同样会进行写入。The detection label file which can be directly used for PPOCR detection model training. After the user saves 10 label results, the program will be automatically written. It will also be written when the user closes the application or switches the file path. |
   | fileState.txt | 图片状态标记文件，保存当前文件夹下已经被用户手动确认过的图片名称。 |
   |  Cache.cach   |              缓存文件。保存模型自动识别的结果。              |
   |  rec_gt.txt   | 识别标签。可直接用于PPOCR识别模型训练。需用户手动点击菜单栏“PaddleOCR” - "保存识别结果"后产生。 |
   |   crop_img    |   识别数据。按照检测框切割后的图片。与rec_gt.txt同时产生。   |

2. 点击“重新识别”后，模型会对图片中的识别结果进行覆盖。因此如果在此之前手动更改过识别结果，有可能在重新识别后产生变动。
3. 



## Related



