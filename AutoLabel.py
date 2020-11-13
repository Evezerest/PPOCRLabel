#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 准备只将原来的界面布局改掉，但发现比较困难
# pyrcc5 -o libs/resources.py resources.qrc
import argparse
import ast
import codecs
import os.path
import platform
import subprocess
import sys
from functools import partial
from collections import defaultdict
import json



# 整个项目放在PaddleOCR/tools目录下
__dir__ = os.path.dirname(os.path.abspath(__file__))
sys.path.append(__dir__)
sys.path.append(os.path.abspath(os.path.join(__dir__, '../..')))

from paddleocr import PaddleOCR

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    # needed for py3+qt4
    # Ref:
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string
    if sys.version_info.major >= 3:
        import sip

        sip.setapi('QVariant', 2)
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from combobox import ComboBox
from libs.constants import *
from libs.utils import *
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.stringBundle import StringBundle
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.autoDialog import AutoDialog
from libs.labelDialog import LabelDialog
from libs.colorDialog import ColorDialog
from libs.labelFile import LabelFile, LabelFileError, LabelFileFormat
from libs.toolBar import ToolBar
from libs.pascal_voc_io import PascalVocReader
from libs.pascal_voc_io import XML_EXT
from libs.yolo_io import YoloReader
from libs.yolo_io import TXT_EXT
from libs.ustr import ustr
from libs.hashableQListWidgetItem import HashableQListWidgetItem

__appname__ = 'AutoLabel'


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):  # 顶和底层
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, defaultFilename=None, defaultPrefdefClassFile=None, defaultSaveDir=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()  # 读入现有的设置
        settings = self.settings

        # Load string bundle for i18n
        self.stringBundle = StringBundle.getBundle(localeStr="zh-CN")
        getStr = lambda strId: self.stringBundle.getString(strId)

        # Save as Pascal voc xml
        self.defaultSaveDir = defaultSaveDir
        # self.labelFileFormat = settings.get(SETTING_LABEL_FILE_FORMAT, LabelFileFormat.PASCAL_VOC)
        self.labelFileFormat = 'Paddle'  # 写死
        self.ocr = PaddleOCR(use_pdserving=False, use_angle_cls=True, det=False, cls=True, lang="ch")  # 读入模型

        # For loading all image under a directory
        self.mImgList = []
        self.dirname = None
        self.labelHist = []
        self.lastOpenDir = None
        self.result_dic = []

        self.changeFileFolder = False
        self.haveAutoReced = False
        self.labelFile = None
        self.currIndex = 0


        # Whether we need to save or not.
        self.dirty = False

        self._noSelectionSlot = False
        self._beginner = True
        self.screencastViewer = self.getAvailableScreencastViewer()
        self.screencast = "https://youtu.be/p0nR2YsCY_U"

        # Load predefined classes to the list
        self.loadPredefinedClasses(defaultPrefdefClassFile)

        # Main widgets and related state.
        self.labelDialog = LabelDialog(parent=self, listItem=self.labelHist)
        self.autoDialog = AutoDialog(parent=self)

        self.itemsToShapes = {}
        self.shapesToItems = {}
        self.itemsToShapesbox = {}
        self.shapesToItemsbox = {}
        self.prevLabelText = '待识别'
        self.model = 'paddle'  # ADD
        self.PPreader = None  # txt标注类

        ################# 文件列表  ###############
        # TODO: 增加icon
        self.fileListWidget = QListWidget()
        self.fileListWidget.itemDoubleClicked.connect(self.fileitemDoubleClicked)  # 文件被双击后
        self.fileListWidget.setIconSize(QSize(25, 25))  # 设置控件大小
        filelistLayout = QVBoxLayout()
        filelistLayout.setContentsMargins(0, 0, 0, 0)
        filelistLayout.addWidget(self.fileListWidget)  # self.verticalLayoutWidget_2

        self.AutoRecognition = QToolButton()
        self.AutoRecognition.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.AutoRecognition.setIcon(newIcon()) # TODO: icon
        autoRecLayout = QHBoxLayout()
        autoRecLayout.setContentsMargins(0, 0, 0, 0)
        autoRecLayout.addWidget(self.AutoRecognition)
        autoRecContainer = QWidget()
        autoRecContainer.setLayout(autoRecLayout)
        filelistLayout.addWidget(autoRecContainer)

        fileListContainer = QWidget()
        fileListContainer.setLayout(filelistLayout)
        self.filedock = QDockWidget(getStr('fileList'), self)  # getStr方便转换
        self.filedock.setObjectName(getStr('files'))
        self.filedock.setWidget(fileListContainer)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.filedock)

        ######## 右侧的整体区域
        listLayout = QVBoxLayout()
        listLayout.setContentsMargins(0, 0, 0, 0)

        # Create a widget for using default label # CheckBox加入到HBoxLayout中 再加入到Qwidget中，最后到VBoxLayout中
        # 这部分以后可以删除
        # self.useDefaultLabelCheckbox = QCheckBox(getStr('useDefaultLabel'))
        # self.useDefaultLabelCheckbox.setChecked(False)
        # self.defaultLabelTextLine = QLineEdit()
        # useDefaultLabelQHBoxLayout = QHBoxLayout()
        # useDefaultLabelQHBoxLayout.addWidget(self.useDefaultLabelCheckbox)
        # useDefaultLabelQHBoxLayout.addWidget(self.defaultLabelTextLine)
        # useDefaultLabelContainer = QWidget()
        # useDefaultLabelContainer.setLayout(useDefaultLabelQHBoxLayout)

        # Create a widget for edit and diffc button
        self.diffcButton = QCheckBox(getStr('useDifficult'))
        self.diffcButton.setChecked(False)
        self.diffcButton.stateChanged.connect(self.btnstate)
        self.editButton = QToolButton()
        self.reRecogButton = QToolButton()
        self.reRecogButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.reRecogButton.setIcon(newIcon()) # TODO
        # 增加一个新建框？或直接将下面的按钮移动到上面
        self.newButton = QToolButton()
        self.newButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.SaveButton = QToolButton()
        self.SaveButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.DelButton = QToolButton()
        self.DelButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # 右侧顶层box
        lefttoptoolbox = QHBoxLayout()
        lefttoptoolbox.addWidget(self.newButton)
        lefttoptoolbox.addWidget(self.reRecogButton)
        lefttoptoolboxcontainer = QWidget()
        lefttoptoolboxcontainer.setLayout(lefttoptoolbox)
        listLayout.addWidget(lefttoptoolboxcontainer)

        # Add some of widgets to listLayout
        # listLayout.addWidget(self.newButton) # ADD
        # listLayout.addWidget(self.editButton)
        listLayout.addWidget(self.diffcButton)
        #listLayout.addWidget(useDefaultLabelContainer)

        # Create and add combobox for showing unique labels in group 显示不同标签用的
        # self.comboBox = ComboBox(self)
        # listLayout.addWidget(self.comboBox)

        ################## label窗 ####################
        # Create and add a widget for showing current label items
        self.labelList = QListWidget()
        labelListContainer = QWidget()
        labelListContainer.setLayout(listLayout)  # 把窗口父化？
        # 信号触发条件
        self.labelList.itemActivated.connect(self.labelSelectionChanged)  # 激活时发出信号
        self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)
        self.labelList.itemDoubleClicked.connect(self.editLabel)
        # Connect to itemChanged to detect checkbox changes.
        self.labelList.itemChanged.connect(self.labelItemChanged)
        self.labelListDock = QDockWidget('识别结果',self)
        self.labelListDock.setWidget(self.labelList)
        self.labelListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        listLayout.addWidget(self.labelListDock)

        ################## 检测窗 ####################
        self.BoxList = QListWidget()
        # BoxListContainer = QWidget()
        # BoxListContainer.setLayout(listLayout)
        # 信号触发条件
        self.BoxList.itemActivated.connect(self.boxSelectionChanged)  # 激活时发出信号
        self.BoxList.itemSelectionChanged.connect(self.boxSelectionChanged)
        self.BoxList.itemDoubleClicked.connect(self.editBox)  # 双击之后更改内容
        # Connect to itemChanged to detect checkbox changes.
        self.BoxList.itemChanged.connect(self.boxItemChanged)
        self.BoxListDock = QDockWidget('检测框位置', self)
        self.BoxListDock.setWidget(self.BoxList)
        self.BoxListDock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        listLayout.addWidget(self.BoxListDock)

        ############ 左侧底层box ############
        leftbtmtoolbox = QHBoxLayout()
        leftbtmtoolbox.addWidget(self.SaveButton)
        leftbtmtoolbox.addWidget(self.DelButton)
        leftbtmtoolboxcontainer = QWidget()
        leftbtmtoolboxcontainer.setLayout(leftbtmtoolbox)
        listLayout.addWidget(leftbtmtoolboxcontainer)

        # 单个dock的命名方式
        self.dock = QDockWidget(getStr('boxLabelText'), self)
        self.dock.setObjectName(getStr('labels'))
        self.dock.setWidget(labelListContainer)

        # 文件窗
        # # ADD
        # self.centralwidget = QWidget() # zheliyouwenti
        # self.centralwidget.setObjectName("centralwidget")
        # self.verticalLayoutWidget_2 = QWidget(self.centralwidget)
        # self.verticalLayoutWidget_2.setGeometry(QtCore.QRect(0, 0, 221, 571))
        # self.verticalLayoutWidget_2.setObjectName("verticalLayoutWidget_2")
        # filelistLayout = QVBoxLayout(self.verticalLayoutWidget_2)
        # filelistLayout.setContentsMargins(0, 0, 0, 0)
        #
        # self.fileListWidget = QListWidget(self.verticalLayoutWidget_2)
        # self.fileListWidget.itemDoubleClicked.connect(self.fileitemDoubleClicked)
        # filelistLayout.addWidget(self.fileListWidget)

        ########## 缩放组件 #########
        self.imgsplider = QSlider(Qt.Horizontal)
        self.imgsplider.valueChanged.connect(self.CanvasSizeChange)
        self.imgsplider.setMinimum(-150)
        self.imgsplider.setMaximum(150)
        self.imgsplider.setSingleStep(1)
        self.imgsplider.setTickPosition(QSlider.TicksBelow)
        self.imgsplider.setTickInterval(1)
        op = QGraphicsOpacityEffect()
        op.setOpacity(0.2)
        self.imgsplider.setGraphicsEffect(op)
        # self.imgsplider.setAttribute(Qt.WA_TranslucentBackground)
        self.imgsliderDock = QDockWidget(getStr('ImageResize'), self)
        self.imgsliderDock.setObjectName(getStr('IR'))
        self.imgsliderDock.setWidget(self.imgsplider)
        self.imgsliderDock.setFeatures(QDockWidget.DockWidgetFloatable)
        # op = QGraphicsOpacityEffect()
        # op.setOpacity(0.2)
        # self.imgsliderDock.setGraphicsEffect(op)
        self.imgsliderDock.setAttribute(Qt.WA_TranslucentBackground)
        self.addDockWidget(Qt.RightDockWidgetArea, self.imgsliderDock)

        self.zoomWidget = ZoomWidget()
        self.colorDialog = ColorDialog(parent=self)
        self.zoomWidgetValue = self.zoomWidget.value()

        ########## 底层缩略图 #########
        hlayout = QHBoxLayout()
        m = (0, 0, 0, 0)
        hlayout.setSpacing(0)
        hlayout.setContentsMargins(*m)
        self.preButton = QToolButton()
        self.preButton.setFixedHeight(100)
        self.preButton.setText(getStr("prevImg"))
        self.preButton.setIcon(newIcon("prev", 80))
        self.preButton.setIconSize(QSize(80, 80))
        self.preButton.clicked.connect(self.openPrevImg)
        self.preButton.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.iconlist = QListWidget()
        self.iconlist.setViewMode(QListView.IconMode)
        self.iconlist.setFlow(QListView.TopToBottom)
        self.iconlist.setSpacing(10)
        self.iconlist.setIconSize(QSize(50, 50))
        self.iconlist.setMovement(False)
        self.iconlist.setResizeMode(QListView.Adjust)
        self.iconlist.itemDoubleClicked.connect(self.iconitemDoubleClicked)
        self.nextButton = QToolButton()
        self.nextButton.setFixedHeight(100)
        self.nextButton.setText(getStr("nextImg"))
        self.nextButton.setIcon(newIcon("next", 80))
        self.nextButton.setIconSize(QSize(80, 80))
        self.nextButton.clicked.connect(self.openNextImg)
        self.nextButton.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        hlayout.addWidget(self.preButton)
        hlayout.addWidget(self.iconlist)
        hlayout.addWidget(self.nextButton)

        # self.setLayout(hlayout)

        iconListContainer = QWidget()
        iconListContainer.setLayout(hlayout)
        iconListContainer.setFixedHeight(100)
        self.icondock = QDockWidget(getStr('iconList'), self)
        self.icondock.setObjectName('icons')
        self.icondock.setWidget(iconListContainer)
        self.icondock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        # self.additems()
        self.addDockWidget(Qt.BottomDockWidgetArea, self.icondock)

        # 框绘制
        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoomRequest)
        self.canvas.setDrawingShapeToSquare(settings.get(SETTING_DRAW_SQUARE, False))

        # 滚动条 图像放大
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
        }
        self.scrollArea = scroll
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.updateBoxlist)  # self.setDirty TODO
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        # 设置docker所放置的区域
        self.setCentralWidget(scroll)
        # self.addDockWidget(Qt.LeftDockWidgetArea, self.filedock) # 这里改了左侧但没用
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)

        # TODO：双击Label之后跳出的界面 不需要备选label，需要更改。将label的单击显示用可展开的形式
        # 改变lineedit之后 函数没有对应的 可能需要重写这部分

        # self.filedock.setFeatures(QDockWidget.DockWidgetFloatable)
        self.filedock.setFeatures(self.filedock.features() ^ QDockWidget.DockWidgetFloatable)  # 改动之后出现关闭按钮

        self.dockFeatures = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

        self.filedock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        ###### Actions
        action = partial(newAction, self)
        quit = action(getStr('quit'), self.close,
                      'Ctrl+Q', 'quit', getStr('quitApp'))

        open = action(getStr('openFile'), self.openFile,
                      'Ctrl+O', 'open', getStr('openFileDetail'))

        opendir = action(getStr('openDir'), self.openDirDialog,
                         'Ctrl+u', 'open', getStr('openDir'))

        # copyPrevBounding = action(getStr('copyPrevBounding'), self.copyPreviousBoundingBoxes,
        #                           'Ctrl+v', 'paste', getStr('copyPrevBounding'))

        changeSavedir = action(getStr('changeSaveDir'), self.changeSavedirDialog,
                               'Ctrl+r', 'open', getStr('changeSavedAnnotationDir'))

        openAnnotation = action(getStr('openAnnotation'), self.openAnnotationDialog,
                                'Ctrl+Shift+O', 'open', getStr('openAnnotationDetail'))

        openNextImg = action(getStr('nextImg'), self.openNextImg,
                             'd', 'next', getStr('nextImgDetail'))

        openPrevImg = action(getStr('prevImg'), self.openPrevImg,
                             'a', 'prev', getStr('prevImgDetail'))

        verify = action(getStr('verifyImg'), self.verifyImg,
                        'space', 'verify', getStr('verifyImgDetail'))

        save = action(getStr('save'), self.saveFile,
                      'Ctrl+S', 'save', getStr('saveDetail'), enabled=False)

        alcm = action(getStr('choosemodel'), self.autolcm,
                      'Ctrl+M', 'next', getStr('tipchoosemodel'))
        isUsingPascalVoc = self.labelFileFormat == LabelFileFormat.PASCAL_VOC
        # save_format = action('&PascalVOC' if isUsingPascalVoc else '&YOLO',
        #                      self.change_format, 'Ctrl+',
        #                      'format_voc' if isUsingPascalVoc else 'format_yolo',
        #                      getStr('changeSaveFormat'), enabled=True)

        # saveAs = action(getStr('saveAs'), self.saveFileAs,
        #                 'Ctrl+Shift+S', 'save-as', getStr('saveAsDetail'), enabled=False)

        # close = action(getStr('closeCur'), self.closeFile, 'Ctrl+W', 'close', getStr('closeCurDetail'))

        deleteImg = action(getStr('deleteImg'), self.deleteImg, 'Ctrl+D', 'close', getStr('deleteImgDetail'))

        resetAll = action(getStr('resetAll'), self.resetAll, None, 'resetall', getStr('resetAllDetail'))

        color1 = action(getStr('boxLineColor'), self.chooseColor1,
                        'Ctrl+L', 'color_line', getStr('boxLineColorDetail'))

        createMode = action(getStr('crtBox'), self.setCreateMode,
                            'w', 'new', getStr('crtBoxDetail'), enabled=False)
        editMode = action('&Edit\nRectBox', self.setEditMode,
                          'Ctrl+J', 'edit', u'Move and edit Boxs', enabled=False)

        create = action(getStr('crtBox'), self.createShape,
                        'w', 'new', getStr('crtBoxDetail'), enabled=False)

        delete = action(getStr('delBox'), self.deleteSelectedShape,
                        'Delete', 'delete', getStr('delBoxDetail'), enabled=False)
        copy = action(getStr('dupBox'), self.copySelectedShape,
                      'Ctrl+D', 'copy', getStr('dupBoxDetail'),
                      enabled=False)

        # advancedMode = action(getStr('advancedMode'), self.toggleAdvancedMode,
        #                       'Ctrl+Shift+A', 'expert', getStr('advancedModeDetail'),
        #                       checkable=True)

        hideAll = action('&Hide\nRectBox', partial(self.togglePolygons, False),
                         'Ctrl+H', 'hide', getStr('hideAllBoxDetail'),
                         enabled=False)
        showAll = action('&Show\nRectBox', partial(self.togglePolygons, True),
                         'Ctrl+A', 'hide', getStr('showAllBoxDetail'),
                         enabled=False)

        help = action(getStr('tutorial'), self.showTutorialDialog, None, 'help', getStr('tutorialDetail'))
        showInfo = action(getStr('info'), self.showInfoDialog, None, 'help', getStr('info'))

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (fmtShortcut("Ctrl+[-+]"),
                                             fmtShortcut("Ctrl+Wheel")))
        self.zoomWidget.setEnabled(False)

        zoomIn = action(getStr('zoomin'), partial(self.addZoom, 10),
                        'Ctrl++', 'zoom-in', getStr('zoominDetail'), enabled=False)
        zoomOut = action(getStr('zoomout'), partial(self.addZoom, -10),
                         'Ctrl+-', 'zoom-out', getStr('zoomoutDetail'), enabled=False)
        zoomOrg = action(getStr('originalsize'), partial(self.setZoom, 100),
                         'Ctrl+=', 'zoom', getStr('originalsizeDetail'), enabled=False)
        fitWindow = action(getStr('fitWin'), self.setFitWindow,
                           'Ctrl+F', 'fit-window', getStr('fitWinDetail'),
                           checkable=True, enabled=False)
        fitWidth = action(getStr('fitWidth'), self.setFitWidth,
                          'Ctrl+Shift+F', 'fit-width', getStr('fitWidthDetail'),
                          checkable=True, enabled=False)
        # Group zoom controls into a list for easier toggling.
        zoomActions = (self.zoomWidget, zoomIn, zoomOut,
                       zoomOrg, fitWindow, fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action(getStr('editLabel'), self.editLabel,
                      'Ctrl+E', 'edit', getStr('editLabelDetail'),
                      enabled=False)
        # print('getStr is ', getStr('editLabel'))
        # Add:

        AutoRec = action(getStr('autoRecognition'), self.autoRecognition, # 新加入按键
                      'Ctrl+Shif+A', 'AutoRecognition', 'Auto Recognition', enabled=False)


        reRec = action(getStr('reRecognition'), self.reRecognition,  # 新加入按键
                       'Ctrl+Shif+R', 'reRecognition', 'reRecognition', enabled=True)

        createpoly = action('Creat Polygon', self.createPolygon,
                            'p', 'new', 'Creat Polygon', enabled=True)  # ADD

        self.editButton.setDefaultAction(edit)
        self.newButton.setDefaultAction(create)  # New: 右侧新增框按钮
        self.DelButton.setDefaultAction(deleteImg)
        self.SaveButton.setDefaultAction(save)
        self.AutoRecognition.setDefaultAction(AutoRec)
        self.reRecogButton.setDefaultAction(reRec)
        # self.preButton.setDefaultAction(openPrevImg)
        # self.nextButton.setDefaultAction(openNextImg)

        ############# Zoom layout ##############
        zoomLayout = QHBoxLayout()
        zoomLayout.addStretch()
        self.zoominButton = QToolButton()
        self.zoominButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.zoominButton.setDefaultAction(zoomIn)
        self.zoomoutButton = QToolButton()
        self.zoomoutButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.zoomoutButton.setDefaultAction(zoomOut)
        self.zoomorgButton = QToolButton()
        self.zoomorgButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.zoomorgButton.setDefaultAction(zoomOrg)
        zoomLayout.addWidget(self.zoominButton)
        zoomLayout.addWidget(self.zoomorgButton)
        zoomLayout.addWidget(self.zoomoutButton)

        zoomContainer = QWidget()
        zoomContainer.setLayout(zoomLayout)
        zoomContainer.setGeometry(0, 0, 30, 150)  # x y w h # 只能加docker？

        shapeLineColor = action(getStr('shapeLineColor'), self.chshapeLineColor,
                                icon='color_line', tip=getStr('shapeLineColorDetail'),
                                enabled=False)
        shapeFillColor = action(getStr('shapeFillColor'), self.chshapeFillColor,
                                icon='color', tip=getStr('shapeFillColorDetail'),
                                enabled=False)

        labels = self.dock.toggleViewAction()
        labels.setText(getStr('showHide'))
        labels.setShortcut('Ctrl+Shift+L')

        # Label list context menu.
        labelMenu = QMenu()
        addActions(labelMenu, (edit, delete))  # 右键内容

        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(
            self.popLabelListMenu)

        # Draw squares/rectangles
        self.drawSquaresOption = QAction('Draw Squares', self)
        self.drawSquaresOption.setShortcut('Ctrl+Shift+R')
        self.drawSquaresOption.setCheckable(True)
        self.drawSquaresOption.setChecked(settings.get(SETTING_DRAW_SQUARE, False))
        self.drawSquaresOption.triggered.connect(self.toogleDrawSquare)

        # Store actions for further handling.
        self.actions = struct(save=save,  open=open,  resetAll=resetAll, deleteImg=deleteImg,
                              lineColor=color1, create=create, delete=delete, edit=edit, copy=copy,
                              # save_format=save_format, saveAs=saveAs,close=close,
                              createMode=createMode, editMode=editMode,
                              shapeLineColor=shapeLineColor, shapeFillColor=shapeFillColor,
                              zoom=zoom, zoomIn=zoomIn, zoomOut=zoomOut, zoomOrg=zoomOrg,
                              fitWindow=fitWindow, fitWidth=fitWidth,
                              zoomActions=zoomActions,
                              fileMenuActions=(
                                  open, opendir, save,  resetAll, quit), # saveAs,close,
                              beginner=(), advanced=(),
                              editMenu=(edit, copy, delete,
                                        None, color1, self.drawSquaresOption, createpoly),  # 编辑菜单
                              beginnerContext=(create, edit, copy, delete),
                              advancedContext=(createMode, editMode, edit, copy,
                                               delete, shapeLineColor, shapeFillColor),
                              onLoadActive=(
                                   create, createMode, editMode),#close,
                              onShapesPresent=(hideAll, showAll)) # saveAs,
        # 菜单栏
        self.menus = struct(
            file=self.menu('&'+getStr('mfile')),
            edit=self.menu('&'+getStr('medit')),
            view=self.menu('&'+getStr('mview')),
            autolabel=self.menu('&PaddleOCR'),
            help=self.menu('&'+getStr('mhelp')),
            recentFiles=QMenu('Open &Recent'),
            labelList=labelMenu)

        # # Auto saving : Enable auto saving if pressing next
        # self.autoSaving = QAction(getStr('autoSaveMode'), self)
        # self.autoSaving.setCheckable(True)
        # self.autoSaving.setChecked(settings.get(SETTING_AUTO_SAVE, False))  # 默认关闭
        # Sync single class mode from PR#106
        self.singleClassMode = QAction(getStr('singleClsMode'), self)
        self.singleClassMode.setShortcut("Ctrl+Shift+S")
        self.singleClassMode.setCheckable(True)
        self.singleClassMode.setChecked(settings.get(SETTING_SINGLE_CLASS, False))
        self.lastLabel = None
        # Add option to enable/disable labels being displayed at the top of bounding boxes
        self.displayLabelOption = QAction(getStr('displayLabel'), self)
        self.displayLabelOption.setShortcut("Ctrl+Shift+P")
        self.displayLabelOption.setCheckable(True)
        self.displayLabelOption.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.displayLabelOption.triggered.connect(self.togglePaintLabelsOption)

        addActions(self.menus.file,
                   (opendir,  changeSavedir, openAnnotation, save,  resetAll, deleteImg, quit))
        #copyPrevBounding,close,saveAs,self.menus.recentFiles,

        addActions(self.menus.help, (help, showInfo))
        addActions(self.menus.view, (
            #self.autoSaving,
            self.singleClassMode,
            self.displayLabelOption,
            labels, None,
            hideAll, showAll, None,
            zoomIn, zoomOut, zoomOrg, None,
            fitWindow, fitWidth))

        addActions(self.menus.autolabel, (alcm, None, help))

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        addActions(self.canvas.menus[0], self.actions.beginnerContext)
        addActions(self.canvas.menus[1], (
            action('&Copy here', self.copyShape),
            action('&Move here', self.moveShape)))

        # self.tools = self.toolbar('Tools')

        # 浮动窗
        self.actions.beginner = (
            open, opendir, changeSavedir, openNextImg, openPrevImg, verify, save, None, create, copy, delete, None,
            zoomIn, zoom, zoomOut, fitWindow, fitWidth)

        self.actions.advanced = (
            open, opendir, changeSavedir, openNextImg, openPrevImg, save, None,
            createMode, editMode, None,
            hideAll, showAll)

        # 状态提示
        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.filePath = ustr(defaultFilename)
        self.lastOpenDir = None
        self.recentFiles = []
        self.maxRecent = 7
        self.lineColor = None
        self.fillColor = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        ## Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recentFileQStringList = settings.get(SETTING_RECENT_FILES)
                self.recentFiles = [ustr(i) for i in recentFileQStringList]
            else:
                self.recentFiles = recentFileQStringList = settings.get(SETTING_RECENT_FILES)

        size = settings.get(SETTING_WIN_SIZE, QSize(600, 1000))
        position = QPoint(0, 0)
        saved_position = settings.get(SETTING_WIN_POSE, position)
        # Fix the multiple monitors issue
        for i in range(QApplication.desktop().screenCount()):
            if QApplication.desktop().availableGeometry(i).contains(saved_position):
                position = saved_position
                break
        self.resize(size)
        self.move(position)
        saveDir = ustr(settings.get(SETTING_SAVE_DIR, None))
        self.lastOpenDir = ustr(settings.get(SETTING_LAST_OPEN_DIR, None))
        if self.defaultSaveDir is None and saveDir is not None and os.path.exists(saveDir):
            self.defaultSaveDir = saveDir
            self.loadFilestate(saveDir)  # 如果不设定 则在loadfile中读取文件时设置
            self.loadPPlabel(saveDir)
            self.statusBar().showMessage('%s started. Annotation will be saved to %s' %
                                         (__appname__, self.defaultSaveDir))
            self.statusBar().show()

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))
        Shape.line_color = self.lineColor = QColor(settings.get(SETTING_LINE_COLOR, DEFAULT_LINE_COLOR))
        Shape.fill_color = self.fillColor = QColor(settings.get(SETTING_FILL_COLOR, DEFAULT_FILL_COLOR))
        self.canvas.setDrawingColor(self.lineColor)
        # Add chris
        Shape.difficult = self.difficult

        # def xbool(x):
        #     if isinstance(x, QVariant):
        #         return x.toBool()
        #     return bool(x)

        # if xbool(settings.get(SETTING_ADVANCE_MODE, False)):
        #     self.actions.advancedMode.setChecked(True)
        #     self.toggleAdvancedMode()

        # ADD:
        # Populate the File menu dynamically.
        self.updateFileMenu()

        # Since loading the file may take some time, make sure it runs in the background.
        if self.filePath and os.path.isdir(self.filePath):
            self.queueEvent(partial(self.importDirImages, self.filePath or ""))
        elif self.filePath:
            self.queueEvent(partial(self.loadFile, self.filePath or ""))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        self.populateModeActions()

        # Display cursor coordinates at the right of status bar
        self.labelCoordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.labelCoordinates)

        # Open Dir if deafult file
        if self.filePath and os.path.isdir(self.filePath):
            self.openDirDialog(dirpath=self.filePath, silent=True)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.canvas.setDrawingShapeToSquare(False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            # Draw rectangle if Ctrl is pressed
            self.canvas.setDrawingShapeToSquare(True)

    ## Support Functions ##
    def set_format(self, save_format):
        if save_format == FORMAT_PASCALVOC:
            self.actions.save_format.setText(FORMAT_PASCALVOC)
            self.actions.save_format.setIcon(newIcon("format_voc"))
            self.labelFileFormat = LabelFileFormat.PASCAL_VOC
            LabelFile.suffix = XML_EXT

        elif save_format == FORMAT_YOLO:
            self.actions.save_format.setText(FORMAT_YOLO)
            self.actions.save_format.setIcon(newIcon("format_yolo"))
            self.labelFileFormat = LabelFileFormat.YOLO
            LabelFile.suffix = TXT_EXT

    def change_format(self):
        if self.labelFileFormat == LabelFileFormat.PASCAL_VOC:
            self.set_format(FORMAT_YOLO)
        elif self.labelFileFormat == LabelFileFormat.YOLO:
            self.set_format(FORMAT_PASCALVOC)
        else:
            raise ValueError('Unknown label file format.')
        self.setDirty()

    def noShapes(self):
        return not self.itemsToShapes

    # def toggleAdvancedMode(self, value=True):
    #     self._beginner = not value
    #     self.canvas.setEditing(True)
    #     self.populateModeActions()
    #     self.editButton.setVisible(not value)
    #     if value:
    #         self.actions.createMode.setEnabled(True)
    #         self.actions.editMode.setEnabled(False)
    #         self.dock.setFeatures(self.dock.features() | self.dockFeatures)
    #     else:
    #         self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

    def populateModeActions(self):
        # toolbar的内容
        # if self.beginner():
        #     tool, menu = self.actions.beginner, self.actions.beginnerContext
        # else:
        #     tool, menu = self.actions.advanced, self.actions.advancedContext
        # self.tools.clear()
        # addActions(self.tools, tool) # 这一步在toolbar增加功能  第一个参数widget中增加第二个参数action
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], self.actions.beginnerContext)
        self.menus.edit.clear()
        actions = (self.actions.create,)  # if self.beginner() else (self.actions.createMode, self.actions.editMode)
        addActions(self.menus.edit, actions + self.actions.editMenu)

    def setBeginner(self):
        # self.tools.clear()
        # addActions(self.tools, self.actions.beginner)
        print("set Beginner")

    def setAdvanced(self):
        # self.tools.clear()
        # addActions(self.tools, self.actions.advanced)
        print("set Beginner")

    def setDirty(self):
        self.dirty = True
        self.actions.save.setEnabled(True)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.create.setEnabled(True)

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.itemsToShapes.clear()
        self.shapesToItems.clear()
        self.itemsToShapesbox.clear()  # ADD
        self.shapesToItemsbox.clear()
        self.labelList.clear()
        self.BoxList.clear()
        self.filePath = None
        self.imageData = None
        self.labelFile = None
        self.canvas.resetState()
        self.labelCoordinates.clear()
        # self.comboBox.cb.clear()
        self.result_dic = []

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def currentBox(self):
        items = self.BoxList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filePath):
        if filePath in self.recentFiles:
            self.recentFiles.remove(filePath)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filePath)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    def getAvailableScreencastViewer(self):
        osName = platform.system()

        if osName == 'Windows':
            return ['C:\\Program Files\\Internet Explorer\\iexplore.exe']
        elif osName == 'Linux':
            return ['xdg-open']
        elif osName == 'Darwin':
            return ['open']

    ## Callbacks ##
    def showTutorialDialog(self):
        subprocess.Popen(self.screencastViewer + [self.screencast])

    def showInfoDialog(self):
        from libs.__init__ import __version__
        msg = u'Name:{0} \nApp Version:{1} \n{2} '.format(__appname__, __version__, sys.version_info)
        QMessageBox.information(self, u'Information', msg)

    def createShape(self):  # 增加框——改变两个状态
        assert self.beginner()
        self.canvas.setEditing(False)
        self.actions.create.setEnabled(False)
        self.canvas.fourpoint = False

    def createPolygon(self):  # 增加框——改变两个状态
        assert self.beginner()
        self.canvas.setEditing(False)
        self.canvas.fourpoint = True
        self.actions.create.setEnabled(False)

    def toggleDrawingSensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            # Cancel creation.
            print('Cancel creation.')
            self.canvas.setEditing(True)
            self.canvas.restoreCursor()
            self.actions.create.setEnabled(True)

    def toggleDrawMode(self, edit=True):
        self.canvas.setEditing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def setCreateMode(self):
        assert self.advanced()
        self.toggleDrawMode(False)

    def setEditMode(self):
        assert self.advanced()
        self.toggleDrawMode(True)
        self.labelSelectionChanged()

    def updateFileMenu(self):
        currFilePath = self.filePath

        def exists(filename):
            return os.path.exists(filename)

        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f !=
                 currFilePath and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon('labels')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.loadRecent, f))
            menu.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    def editLabel(self):  # 双击之后
        if not self.canvas.editing():
            return
        item = self.currentItem()
        if not item:
            return
        text = self.labelDialog.popUp(item.text())
        if text is not None:
            item.setText(text)
            item.setBackground(generateColorByText(text))
            self.setDirty()
            self.updateComboBox()  # 更新候选

    ######## 检测框相关函数 #######

    def boxItemChanged(self, item):
        shape = self.itemsToShapesbox[item]  # 连接到目标shape
        # TODO: 需要对内容增加判断条件
        box = ast.literal_eval(item.text())  # str转list
        # print('shape in labelItemChanged is',shape.points)
        if box != [(p.x(), p.y()) for p in shape.points]:  # label发生变化，需要重新写入
            # shape.points = box # 写入point的数据类型？
            shape.points = [QPointF(p[0], p[1]) for p in box]

            # QPointF(x,y)
            shape.line_color = generateColorByText(shape.label)
            self.setDirty()
        else:  # User probably changed item visibility
            self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    def editBox(self):  # ADD
        if not self.canvas.editing():
            return
        item = self.currentBox()
        if not item:
            return
        text = self.labelDialog.popUp(item.text())  # 设置文字
        # 判断输入是否符合图片大小
        imageSize = str(self.image.size())
        width, height = self.image.width(), self.image.height()
        try:
            text_list = eval(text)
        except:
            msg_box = QMessageBox(QMessageBox.Warning, '警告', '请输入正确的格式')
            msg_box.exec_()
            return
        if len(text_list) < 4:
            msg_box = QMessageBox(QMessageBox.Warning, '警告', '请输入4个点的坐标')
            msg_box.exec_()
            return
        for box in text_list:
            if box[0] > width or box[0] < 0 or box[1] > height or box[1] < 0:
                msg_box = QMessageBox(QMessageBox.Warning, '警告', '超出图片范围')
                msg_box.exec_()
                return
        if text is not None:
            item.setText(text)  # 这里会连接到labelItemChanged
            item.setBackground(generateColorByText(text))
            self.setDirty()
            self.updateComboBox()  # 更新候选

    def updateBoxlist(self):
        # 更新list中的坐标
        shape = self.canvas.selectedShape  # 这边还需要选定当前的shape框
        item = self.shapesToItemsbox[shape]  # listitem
        text = [(int(p.x()), int(p.y())) for p in shape.points]
        item.setText(str(text))
        self.setDirty()

    # Tzutalin 20160906 : Add file list and dock to move faster
    def fileitemDoubleClicked(self, item=None):
        chosenIdx = self.mImgList.index(ustr(os.path.join(os.path.abspath(self.dirname), item.text())))
        if self.currIndex == chosenIdx:
            pass
        else:
            self.currIndex = chosenIdx
            filename = self.mImgList[self.currIndex]
            if filename:
                self.loadFile(filename)

    def iconitemDoubleClicked(self, item=None):
        # currIndex = self.mImgList.index(ustr(os.path.join(item.toolTip())))  # TODO:两种形式那种快？
        # if currIndex < len(self.mImgList):
        #     filename = self.mImgList[currIndex]
        chosenIdx = self.mImgList.index(ustr(os.path.join(item.toolTip())))
        # chosenIdx = self.mImgList.index(ustr(os.path.join(os.path.abspath(self.dirname), item.text())))
        if self.currIndex == chosenIdx:
            pass
        else:
            self.currIndex = chosenIdx
            filename = self.mImgList[self.currIndex]
            if filename:
                self.loadFile(filename)

    def CanvasSizeChange(self):
        if len(self.mImgList) > 0:
            self.zoomWidget.setValue(self.zoomWidgetValue + self.imgsplider.value())

    # Add chris
    def btnstate(self, item=None):
        """ Function to handle difficult examples
        Update on each object """
        if not self.canvas.editing():
            return

        item = self.currentItem()
        if not item:  # If not selected Item, take the first one
            item = self.labelList.item(self.labelList.count() - 1)

        difficult = self.diffcButton.isChecked()

        try:
            shape = self.itemsToShapes[item]
        except:
            pass
        # Checked and Update
        try:
            if difficult != shape.difficult:
                shape.difficult = difficult
                self.setDirty()
            else:  # User probably changed item visibility
                self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)
        except:
            pass

    # React to canvas signals.
    def shapeSelectionChanged(self, selected=False):
        if self._noSelectionSlot:
            self._noSelectionSlot = False
        else:
            shape = self.canvas.selectedShape
            if shape:
                self.shapesToItems[shape].setSelected(True)
                self.shapesToItemsbox[shape].setSelected(True)  # ADD
            else:
                self.labelList.clearSelection()
        self.actions.delete.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.edit.setEnabled(selected)
        self.actions.shapeLineColor.setEnabled(selected)
        self.actions.shapeFillColor.setEnabled(selected)

    def addLabel(self, shape):  #
        shape.paintLabel = self.displayLabelOption.isChecked()
        item = HashableQListWidgetItem(shape.label)  # 这个类只能添加str
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setBackground(generateColorByText(shape.label))
        self.itemsToShapes[item] = shape  # 两个dict 相互连接
        self.shapesToItems[shape] = item
        self.labelList.addItem(item)
        # print('item in add label is ',[(p.x(), p.y()) for p in shape.points], shape.label)

        # ADD for box
        item = HashableQListWidgetItem(str([(p.x(), p.y()) for p in shape.points]))  # 这里可以转化一下
        # item = QListWidgetItem(str([(p.x(), p.y()) for p in shape.points]))
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)  # 状态
        item.setBackground(generateColorByText(shape.label))  # 背景颜色
        self.itemsToShapesbox[item] = shape
        self.shapesToItemsbox[shape] = item
        self.BoxList.addItem(item)
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)
        self.updateComboBox()

    def remLabel(self, shape):
        if shape is None:
            # print('rm empty label')
            return
        item = self.shapesToItems[shape]
        self.labelList.takeItem(self.labelList.row(item))
        del self.shapesToItems[shape]
        del self.itemsToShapes[item]
        self.updateComboBox()

        # ADD:
        item = self.shapesToItemsbox[shape]
        self.BoxList.takeItem(self.BoxList.row(item))
        del self.shapesToItemsbox[shape]
        del self.itemsToShapesbox[item]
        self.updateComboBox()

    def loadLabels(self, shapes):
        s = []
        for label, points, line_color, fill_color, difficult in shapes:
            shape = Shape(label=label)
            for x, y in points:

                # Ensure the labels are within the bounds of the image. If not, fix them.
                x, y, snapped = self.canvas.snapPointToCanvas(x, y)
                if snapped:
                    self.setDirty()

                shape.addPoint(QPointF(x, y))
            shape.difficult = difficult
            shape.close()
            s.append(shape)

            if line_color:
                shape.line_color = QColor(*line_color)
            else:
                shape.line_color = generateColorByText(label)

            if fill_color:
                shape.fill_color = QColor(*fill_color)
            else:
                shape.fill_color = generateColorByText(label)

            self.addLabel(shape)
        self.updateComboBox()
        self.canvas.loadShapes(s)

    def updateComboBox(self):  # 在备选栏中更新不同的标签
        # Get the unique labels and add them to the Combobox.
        itemsTextList = [str(self.labelList.item(i).text()) for i in range(self.labelList.count())]

        uniqueTextList = list(set(itemsTextList))
        # Add a null row for showing all the labels
        uniqueTextList.append("")
        uniqueTextList.sort()

        # self.comboBox.update_items(uniqueTextList)

    def saveLabels(self, annotationFilePath, mode='Auto'):  # annotation对txt无效了
        # mode = auto 则不从canvas中读取 且识别到空字符时不写入, Manual即手动点击保存按钮
        # 从canvas中读取shapes保存到annotationFIle中

        annotationFilePath = ustr(annotationFilePath)
        if self.labelFile is None:
            self.labelFile = LabelFile()  # 新建一个实例
            self.labelFile.verified = self.canvas.verified  # 都是False

        def format_shape(s):
            # print('s in saveLabels is ',s)
            return dict(label=s.label,  # str
                        line_color=s.line_color.getRgb(),
                        fill_color=s.fill_color.getRgb(),
                        points=[(p.x(), p.y()) for p in s.points],  # QPonitF
                        # add chris
                        difficult=s.difficult)  # bool

        # result是对shape的进一步简化， 手动保存时会出现框颜色
        shapes = [] if mode == 'Auto' else \
            [format_shape(shape) for shape in self.canvas.shapes]  # 从canvas中读入shape的内容是有line的
        # Can add differrent annotation formats here

        if self.model == 'paddle':
            for box in self.result_dic:
                # if len(box)==1: # 只有框
                #     trans_dic = {"label": ' ', "points": box[0], 'difficult': False}
                trans_dic = {"label": box[1][0], "points": box[0], 'difficult': False}
                if trans_dic["label"] is "" and mode == 'Auto':
                    continue
                shapes.append(trans_dic)

        try:
            if self.labelFileFormat == LabelFileFormat.PASCAL_VOC:
                if annotationFilePath[-4:].lower() != ".xml":
                    annotationFilePath += XML_EXT
                self.labelFile.savePascalVocFormat(annotationFilePath, shapes, self.filePath, self.imageData,
                                                   self.lineColor.getRgb(), self.fillColor.getRgb())
            elif self.labelFileFormat == LabelFileFormat.YOLO:
                if annotationFilePath[-4:].lower() != ".txt":
                    annotationFilePath += TXT_EXT
                self.labelFile.saveYoloFormat(annotationFilePath, shapes, self.filePath, self.imageData, self.labelHist,
                                              self.lineColor.getRgb(), self.fillColor.getRgb())
            elif self.labelFileFormat == 'Paddle':
                trans_dic = []
                for box in shapes:  # 转换格式 手动点击保存时result为0.应从shapes中读入
                    # if len(box)==1: # 只有框
                    #     trans_dic = {"label": ' ', "points": box[0], 'difficult': False}
                    trans_dic.append({"transcription": box['label'], "points": box['points'], 'difficult': False})
                self.PPlabel[annotationFilePath] = trans_dic

            else:
                self.labelFile.save(annotationFilePath, shapes, self.filePath, self.imageData,
                                    self.lineColor.getRgb(), self.fillColor.getRgb())
            print('Image:{0} -> Annotation:{1}'.format(self.filePath, annotationFilePath))
            return True
        except LabelFileError as e:
            self.errorMessage(u'Error saving label data', u'<b>%s</b>' % e)
            return False

    def copySelectedShape(self):
        self.addLabel(self.canvas.copySelectedShape())
        # fix copy and delete
        self.shapeSelectionChanged(True)

    # def comboSelectionChanged(self, index):
    #     text = self.comboBox.cb.itemText(index)
    #     for i in range(self.labelList.count()):
    #         if text == "":
    #             self.labelList.item(i).setCheckState(2)
    #         elif text != self.labelList.item(i).text():
    #             self.labelList.item(i).setCheckState(0)
    #         else:
    #             self.labelList.item(i).setCheckState(2)

    def labelSelectionChanged(self):
        item = self.currentItem()
        if item and self.canvas.editing():
            self._noSelectionSlot = True
            self.canvas.selectShape(self.itemsToShapes[item])
            shape = self.itemsToShapes[item]
            # Add Chris
            self.diffcButton.setChecked(shape.difficult)

    def boxSelectionChanged(self):
        item = self.currentBox()
        if item and self.canvas.editing():
            self._noSelectionSlot = True
            self.canvas.selectShape(self.itemsToShapesbox[item])
            shape = self.itemsToShapesbox[item]
            # Add Chris
            self.diffcButton.setChecked(shape.difficult)

    def labelItemChanged(self, item):
        shape = self.itemsToShapes[item]  # 连接到目标shape
        label = item.text()
        if label != shape.label:  # label发生变化，需要重新写入
            shape.label = item.text()
            shape.line_color = generateColorByText(shape.label)
            self.setDirty()
        else:  # User probably changed item visibility
            self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    # Callback functions:
    def newShape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        # if not self.useDefaultLabelCheckbox.isChecked() or not self.defaultLabelTextLine.text():
        #     if len(self.labelHist) > 0:
        #         self.labelDialog = LabelDialog(
        #             parent=self, listItem=self.labelHist)

        #     # Sync single class mode from PR#106
        #     if self.singleClassMode.isChecked() and self.lastLabel:
        #         text = self.lastLabel
        #     else:
        #         text = self.labelDialog.popUp(text=self.prevLabelText)
        #         self.lastLabel = text
        # else:
        #     text = self.defaultLabelTextLine.text()
        if len(self.labelHist) > 0:
                self.labelDialog = LabelDialog(
                    parent=self, listItem=self.labelHist)

        # Sync single class mode from PR#106
        if self.singleClassMode.isChecked() and self.lastLabel:
            text = self.lastLabel
        else:
            text = self.labelDialog.popUp(text=self.prevLabelText)
            self.lastLabel = text

        # Add Chris
        self.diffcButton.setChecked(False)
        if text is not None:
            # 不显示上一个label
            self.prevLabelText = '待识别'
            generate_color = generateColorByText(text)
            shape = self.canvas.setLastLabel(text, generate_color, generate_color)
            self.addLabel(shape)
            if self.beginner():  # Switch to edit mode.
                self.canvas.setEditing(True)
                self.actions.create.setEnabled(True)
            else:
                self.actions.editMode.setEnabled(True)
            self.setDirty()

            # 不显示历史标注列表
            # if text not in self.labelHist:
            #     self.labelHist.append(text)
        else:
            # self.canvas.undoLastLine()
            self.canvas.resetAllLines()

    def scrollRequest(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scrollBars[orientation]
        bar.setValue(bar.value() + bar.singleStep() * units)

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)

    def addZoom(self, increment=10):
        self.setZoom(self.zoomWidget.value() + increment)

    def zoomRequest(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scrollBars[Qt.Horizontal]
        v_bar = self.scrollBars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scrollArea.width()
        h = self.scrollArea.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta / (8 * 15)
        scale = 10
        self.addZoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = h_bar.value() + move_x * d_h_bar_max
        new_v_bar_value = v_bar.value() + move_y * d_v_bar_max

        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def togglePolygons(self, value):
        for item, shape in self.itemsToShapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def loadFile(self, filePath=None):  # 读入单张图片
        """Load the specified file, or the last opened file if None."""
        self.resetState()  # 每次双击之后为什么都需要重新设置状态？
        self.canvas.setEnabled(False)
        if filePath is None:
            filePath = self.settings.get(SETTING_FILENAME)

        # Make sure that filePath is a regular python string, rather than QString
        filePath = ustr(filePath)
        # Fix bug: An index error after select a directory when open a new file.
        unicodeFilePath = ustr(filePath)  # 路径
        # unicodeFilePath = os.path.abspath(unicodeFilePath)
        # Tzutalin 20160906 : Add file list and dock to move faster
        # Highlight the file item
        if unicodeFilePath and self.fileListWidget.count() > 0:
            if unicodeFilePath in self.mImgList:
                index = self.mImgList.index(unicodeFilePath)  # 序号
                fileWidgetItem = self.fileListWidget.item(index)
                print('unicodeFilePath is', unicodeFilePath)
                fileWidgetItem.setSelected(True)  # 设计一个选中

                iconWidgetItem = self.iconlist.item(index)
                iconWidgetItem.setSelected(True)
                self.iconlist.scrollToItem(iconWidgetItem)
            else:
                self.fileListWidget.clear()
                self.mImgList.clear()
                self.iconlist.clear()

        # if unicodeFilePath and self.iconList.count() > 0:
        #     if unicodeFilePath in self.mImgList:

        if unicodeFilePath and os.path.exists(unicodeFilePath):
            if LabelFile.isLabelFile(unicodeFilePath):  # 是否是label文件
                try:
                    self.labelFile = LabelFile(unicodeFilePath)  # 读入Label，输入png
                except LabelFileError as e:
                    self.errorMessage(u'Error opening file',
                                      (u"<p><b>%s</b></p>"
                                       u"<p>Make sure <i>%s</i> is a valid label file.")
                                      % (e, unicodeFilePath))
                    self.status("Error reading %s" % unicodeFilePath)
                    return False
                self.imageData = self.labelFile.imageData
                self.lineColor = QColor(*self.labelFile.lineColor)
                self.fillColor = QColor(*self.labelFile.fillColor)
                self.canvas.verified = self.labelFile.verified
            else:
                # Load image:
                # read data first and store for saving into label file.
                self.imageData = read(unicodeFilePath, None)
                self.labelFile = None  # 说明不是label文件
                self.canvas.verified = False

            image = QImage.fromData(self.imageData)
            if image.isNull():
                self.errorMessage(u'Error opening file',
                                  u"<p>Make sure <i>%s</i> is a valid image file." % unicodeFilePath)
                self.status("Error reading %s" % unicodeFilePath)
                return False
            self.status("Loaded %s" % os.path.basename(unicodeFilePath))
            self.image = image
            self.filePath = unicodeFilePath
            self.canvas.loadPixmap(QPixmap.fromImage(image))  # 获得一些size信息
            if self.labelFile:
                self.loadLabels(self.labelFile.shapes)
            if self.validFilestate(filePath) is True:  # 根据当前图片状态确定保存按钮
                self.setClean()
            else:
                self.setDirty()
            self.canvas.setEnabled(True)
            self.adjustScale(initial=True)
            self.paintCanvas()
            self.addRecentFile(self.filePath)
            self.toggleActions(True)
            # self.showBoundingBoxFromAnnotationFile(filePath) # 前提是已经有，打开现有文件的label
            # TODO: 先看一下按这样做需不需要动canvas部分
            self.showBoundingBoxFromPPlabel(filePath)

            self.setWindowTitle(__appname__ + ' ' + filePath)

            # Default : select last item if there is at least one item 这里如果保存了就不需要再减1了
            if self.labelList.count():
                self.labelList.setCurrentItem(self.labelList.item(self.labelList.count() - 1))
                self.labelList.item(self.labelList.count() - 1).setSelected(True)

            self.canvas.setFocus(True)
            return True
        return False

    def showBoundingBoxFromAnnotationFile(self, filePath):
        if self.defaultSaveDir is not None:  #
            basename = os.path.basename(
                os.path.splitext(filePath)[0])
            xmlPath = os.path.join(self.defaultSaveDir, basename + XML_EXT)
            # txtPath = os.path.join(self.defaultSaveDir, basename + TXT_EXT) # 不按单个文件读入
            txtPath = self.defaultSaveDir + '/label.txt'  # 写死label文件

            """Annotation file priority:
            PascalXML > YOLO
            """
            if os.path.isfile(xmlPath):
                self.loadPascalXMLByFilename(xmlPath)
            elif os.path.isfile(txtPath):
                self.loadYOLOTXTByFilename(txtPath)
        else:
            xmlPath = os.path.splitext(filePath)[0] + XML_EXT
            txtPath = os.path.splitext(filePath)[0] + '/label.txt'  # 写死label文件
            if os.path.isfile(xmlPath):
                self.loadPascalXMLByFilename(xmlPath)
            elif os.path.isfile(txtPath):
                self.loadYOLOTXTByFilename(txtPath)

    def showBoundingBoxFromPPlabel(self, filePath):
        # filePath格式 完整E:\\
        imgidx = self.getImglabelidx(filePath)
        if imgidx not in self.PPlabel.keys():
            return
        shapes = []
        for box in self.PPlabel[imgidx]:
            shapes.append((box['transcription'], box['points'], None, None, box['difficult']))

        print(shapes)
        self.loadLabels(shapes)
        self.canvas.verified = False  # 这句的含义？

    def validAnnoExist(self, filePath):
        if self.defaultSaveDir is not None:
            basename = os.path.basename(
                os.path.splitext(filePath)[0])
            xmlPath = os.path.join(self.defaultSaveDir, basename + XML_EXT)
            txtPath = os.path.join(self.defaultSaveDir, basename + TXT_EXT)
            """Annotation file priority:
            PascalXML > YOLO
            """
            if os.path.isfile(xmlPath):
                return True
            elif os.path.isfile(txtPath):
                return True
        else:
            xmlPath = os.path.splitext(filePath)[0] + XML_EXT
            txtPath = os.path.splitext(filePath)[0] + TXT_EXT
            if os.path.isfile(xmlPath):
                return True
            elif os.path.isfile(txtPath):
                return True

    def validFilestate(self, filePath):
        # filePath 格式 path/img.jpg
        if filePath not in self.fileStatedict.keys(): # 如果没有标记
            return None
        elif self.fileStatedict[filePath] == 1: # 如果有标记且保存过
            return True
        else: # 有标记但没保存
            return False  # 自动标记过但没保存

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull() \
                and self.zoomMode != self.MANUAL_ZOOM:
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(int(100 * value))

    def scaleFitWindow(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        settings = self.settings
        # If it loads images from dir, don't load it at the begining
        if self.dirname is None:
            settings[SETTING_FILENAME] = self.filePath if self.filePath else ''
        else:
            settings[SETTING_FILENAME] = ''

        # 将当前的状态保存，下次使用
        settings[SETTING_WIN_SIZE] = self.size()
        settings[SETTING_WIN_POSE] = self.pos()
        settings[SETTING_WIN_STATE] = self.saveState()
        settings[SETTING_LINE_COLOR] = self.lineColor
        settings[SETTING_FILL_COLOR] = self.fillColor
        settings[SETTING_RECENT_FILES] = self.recentFiles
        settings[SETTING_ADVANCE_MODE] = not self._beginner
        if self.defaultSaveDir and os.path.exists(self.defaultSaveDir):
            settings[SETTING_SAVE_DIR] = ustr(self.defaultSaveDir)
        else:
            settings[SETTING_SAVE_DIR] = ''

        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            settings[SETTING_LAST_OPEN_DIR] = self.lastOpenDir
        else:
            settings[SETTING_LAST_OPEN_DIR] = ''

        # settings[SETTING_AUTO_SAVE] = self.autoSaving.isChecked()
        settings[SETTING_SINGLE_CLASS] = self.singleClassMode.isChecked()
        settings[SETTING_PAINT_LABEL] = self.displayLabelOption.isChecked()
        settings[SETTING_DRAW_SQUARE] = self.drawSquaresOption.isChecked()
        settings[SETTING_LABEL_FILE_FORMAT] = self.labelFileFormat
        settings.save()
        self.saveFilestate()  # 保存图片状态
        self.savePPlabel()  # 标签

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = ['.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        images = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.join(root, file)
                    path = ustr(os.path.abspath(relativePath))
                    images.append(path)
        natural_sort(images, key=lambda x: x.lower())
        return images

    def changeSavedirDialog(self, _value=False):
        if self.defaultSaveDir is not None:
            path = ustr(self.defaultSaveDir)
        else:
            path = '.'

        dirpath = ustr(QFileDialog.getExistingDirectory(self,
                                                        '%s - Save annotations to the directory' % __appname__, path,
                                                        QFileDialog.ShowDirsOnly
                                                        | QFileDialog.DontResolveSymlinks))

        if dirpath is not None and len(dirpath) > 1:
            self.defaultSaveDir = dirpath

        self.statusBar().showMessage('%s . Annotation will be saved to %s' %
                                     ('Change saved folder', self.defaultSaveDir))
        self.statusBar().show()

    def openAnnotationDialog(self, _value=False):
        if self.filePath is None:
            self.statusBar().showMessage('Please select image first')
            self.statusBar().show()
            return

        path = os.path.dirname(ustr(self.filePath)) \
            if self.filePath else '.'
        if self.labelFileFormat == LabelFileFormat.PASCAL_VOC:
            filters = "Open Annotation XML file (%s)" % ' '.join(['*.xml'])
            filename = ustr(QFileDialog.getOpenFileName(self, '%s - Choose a xml file' % __appname__, path, filters))
            if filename:
                if isinstance(filename, (tuple, list)):
                    filename = filename[0]
            self.loadPascalXMLByFilename(filename)

    def openDirDialog(self, _value=False, dirpath=None, silent=False):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else '.'
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = os.path.dirname(self.filePath) if self.filePath else '.'
        if silent != True:
            targetDirPath = ustr(QFileDialog.getExistingDirectory(self,
                                                                  '%s - Open Directory' % __appname__,
                                                                  defaultOpenDirPath,
                                                                  QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        else:
            targetDirPath = ustr(defaultOpenDirPath)
        self.lastOpenDir = targetDirPath
        self.importDirImages(targetDirPath)

    def importDirImages(self, dirpath):  # 从dir中读入图片到listWidget中
        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.dirname = dirpath
        if self.defaultSaveDir is None: # 第一次打开时为空
            self.defaultSaveDir = dirpath
            self.loadFilestate(self.defaultSaveDir)
            self.loadPPlabel(self.defaultSaveDir)
        self.filePath = None
        self.fileListWidget.clear()
        self.mImgList = self.scanAllImages(dirpath)  # 将所有文件读入mImgList中
        self.openNextImg()
        # item = QtWidgets.QListWidgetItem(QtGui.QIcon('C:\\Users\Administrator\Desktop\xxx.jpg'), '新建项目')
        for imgPath in self.mImgList:  # 将文件路径读入item
            filename = os.path.basename(imgPath)  # imgPath E:\\全路径，可以改用filename
            if self.validFilestate(imgPath) is True:
                item = QListWidgetItem(newIcon('done'), filename)  # item即为file name的控件
            else:
                item = QListWidgetItem(newIcon('close'), filename)
            self.fileListWidget.addItem(item)

        print('dirPath in importDirImages is', dirpath)
        self.iconlist.clear()
        self.additems(dirpath)
        self.changeFileFolder = True
        self.haveAutoReced = False
        self.AutoRecognition.setEnabled(True)
        # AutoRec.setEnabled(True) # TODO: 刚开始时应该不能点击

    def verifyImg(self, _value=False):
        # Proceding next image without dialog if having any label
        if self.filePath is not None:
            try:
                self.labelFile.toggleVerify()
            except AttributeError:
                # If the labelling file does not exist yet, create if and
                # re-save it with the verified attribute.
                self.saveFile()
                if self.labelFile != None:
                    self.labelFile.toggleVerify()
                else:
                    return

            self.canvas.verified = self.labelFile.verified
            self.paintCanvas()
            self.saveFile()

    def openPrevImg(self, _value=False):
        # Proceding prev image without dialog if having any label
        # if self.autoSaving.isChecked():
        #     if self.defaultSaveDir is not None:
        #         if self.dirty is True:
        #             self.saveFile()
        #     else:
        #         self.changeSavedirDialog()
        #         return

        # if not self.mayContinue():
        #     return

        if len(self.mImgList) <= 0:
            return

        if self.filePath is None:
            return

        currIndex = self.mImgList.index(self.filePath)
        if currIndex - 1 >= 0:
            filename = self.mImgList[currIndex - 1]
            if filename:
                self.loadFile(filename)

    def openNextImg(self, _value=False):
        # # Proceding prev image without dialog if having any label 删除自动保存模式
        # if self.autoSaving.isChecked():
        #     if self.defaultSaveDir is not None:
        #         if self.dirty is True:
        #             self.saveFile()
        #     else:
        #         self.changeSavedirDialog()
        #         return

        # if not self.mayContinue(): # 不需要判断是否继续
        #     return

        if len(self.mImgList) <= 0:
            return

        filename = None
        if self.filePath is None:
            filename = self.mImgList[0]
        else:
            currIndex = self.mImgList.index(self.filePath)
            if currIndex + 1 < len(self.mImgList):
                filename = self.mImgList[currIndex + 1]

        if filename:
            print('file name in openNext is ', filename)
            self.loadFile(filename)

    def openFile(self, _value=False):  # 打开单张
        if not self.mayContinue():
            return
        path = os.path.dirname(ustr(self.filePath)) if self.filePath else '.'
        formats = ['*.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        filters = "Image & Label files (%s)" % ' '.join(formats + ['*%s' % LabelFile.suffix])
        filename = QFileDialog.getOpenFileName(self, '%s - Choose Image or Label file' % __appname__, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.loadFile(filename)
            # print('filename in openfile is ', self.filePath)
        self.filePath = None
        self.fileListWidget.clear()
        self.iconlist.clear()
        self.mImgList = [filename]  # 将所有文件读入mImgList中
        self.openNextImg()
        if self.validFilestate(filename) is True:  # 这里标记改为读入文件
            item = QListWidgetItem(newIcon('done'), filename)
            self.setClean()  # 默认不需要保存
        elif self.validFilestate(filename) is None:
            item = QListWidgetItem(newIcon('close'), filename)
        else: # 没有被保存过
            item = QListWidgetItem(newIcon('close'), filename)
            self.setDirty()
        self.fileListWidget.addItem(filename)
        self.additems(None)
        print('opened image is', filename)

    def updateFileListIcon(self, filename):
        pass

    def saveFile(self, _value=False, mode='Manual'):
        # mode 为Auto 不更新状态，与Manual 更新状态 两种， 默认为不更新状态，只有手动点击Save才保存
        if self.defaultSaveDir is not None and len(ustr(self.defaultSaveDir)):
            if self.filePath:
                # imgFileName = os.path.basename(self.filePath)
                # savedFileName = os.path.splitext(imgFileName)[0]
                # savedPath = os.path.join(ustr(self.defaultSaveDir), savedFileName)
                # self._saveFile(savedPath, mode=mode)
                # 这里输入直接改成 path/img.jpg
                path_list = self.filePath.split('\\')
                imgidx = path_list[-2] + '/' + path_list[-1]
                self._saveFile(imgidx, mode=mode)

        else:  # 如果没有设置则默认选择图片路径
            imgFileDir = os.path.dirname(self.filePath)
            imgFileName = os.path.basename(self.filePath)
            savedFileName = os.path.splitext(imgFileName)[0]
            savedPath = os.path.join(imgFileDir, savedFileName)
            self._saveFile(savedPath if self.labelFile
                           else self.saveFileDialog(removeExt=False), mode=mode)
            # TODO：写入后都需要更新yolo类？

    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._saveFile(self.saveFileDialog())

    def saveFileDialog(self, removeExt=True):
        caption = '%s - Choose File' % __appname__
        filters = 'File (*%s)' % LabelFile.suffix
        openDialogPath = self.currentPath()
        dlg = QFileDialog(self, caption, openDialogPath, filters)
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        filenameWithoutExtension = os.path.splitext(self.filePath)[0]
        dlg.selectFile(filenameWithoutExtension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            fullFilePath = ustr(dlg.selectedFiles()[0])
            if removeExt:
                return os.path.splitext(fullFilePath)[0]  # Return file path without the extension.
            else:
                return fullFilePath
        return ''

    def _saveFile(self, annotationFilePath, mode='Manual'):  # 根据路径保存标记文件，并在文件名前新增图标
        # Auto模式下不显示文件名前的标记
        if mode == 'Manual':  # 手动保存时才对图片状态进行改变（文件名称前显示图标）
            if annotationFilePath and self.saveLabels(annotationFilePath, mode=mode):  # 如果都存在
                self.setClean()
                self.statusBar().showMessage('Saved to  %s' % annotationFilePath)
                self.statusBar().show()
                # 删除之前的项 放入新的项？
                currIndex = self.mImgList.index(self.filePath)
                # item = QListWidgetItem(QtGui.QIcon('./Thano.jpg'), self.mImgList[currIndex]) # 新增项
                # item = QListWidgetItem(self.mImgList[currIndex])
                item = self.fileListWidget.item(currIndex)
                item.setIcon(newIcon('done'))
                # 文件状态与label
                #  将状态设置为 1
                self.fileStatedict[self.filePath] = 1
                print('infor in _saveFile are', currIndex, self.mImgList[currIndex])

                # 直接改变，找到当前item
                # item_pre = self.fileListWidget.currentItem()
                item_prou = self.fileListWidget.item(currIndex)  # 之前项
                # self.fileListWidget.removeItemWidget(self.fileListWidget.row(item_pre)) # 删不掉
                self.fileListWidget.takeItem(self.fileListWidget.row(item_prou))  # 使用take 删除
                print(item_prou)
                print('self.filePath is ', self.filePath)
                # self.fileListWidget.currentItemChanged(item, item_pre) # 用了就崩溃

                self.fileListWidget.insertItem(int(currIndex), item)

        elif mode == 'Auto':  # 全部自动识别下的保存,不更新图片状态
            if annotationFilePath and self.saveLabels(annotationFilePath, mode=mode):
                self.setClean()
                self.statusBar().showMessage('Saved to  %s' % annotationFilePath)
                self.statusBar().show()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def deleteImg(self):
        deletePath = self.filePath
        if deletePath is not None:
            os.remove(deletePath)
            if self.filePath in self.fileStatedict.keys():
                self.fileStatedict.pop(self.filePath)  # 全路径
            imgidx = self.getImglabelidx(self.filePath)
            if imgidx in self.PPlabel.keys():
                self.PPlabel.pop(imgidx)  # 图片路径
            self.openNextImg()
            self.importDirImages(self.lastOpenDir)

    def resetAll(self):
        self.settings.reset()
        self.close()
        proc = QProcess()
        proc.startDetached(os.path.abspath(__file__))

    def mayContinue(self):  #
        if not self.dirty:
            return True
        else:
            discardChanges = self.discardChangesDialog()
            if discardChanges == QMessageBox.No:
                return True
            elif discardChanges == QMessageBox.Yes:
                self.saveFile()
                return True
            else:
                return False

    def discardChangesDialog(self):
        yes, no, cancel = QMessageBox.Yes, QMessageBox.No, QMessageBox.Cancel
        msg = u'You have unsaved changes, would you like to save them and proceed?\nClick "No" to undo all changes.'
        return QMessageBox.warning(self, u'Attention', msg, yes | no | cancel)

    def errorMessage(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def currentPath(self):
        return os.path.dirname(self.filePath) if self.filePath else '.'

    def chooseColor1(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.lineColor = color
            Shape.line_color = color
            self.canvas.setDrawingColor(color)
            self.canvas.update()
            self.setDirty()

    def deleteSelectedShape(self):
        self.remLabel(self.canvas.deleteSelected())
        self.setDirty()
        if self.noShapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)

    def chshapeLineColor(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.canvas.selectedShape.line_color = color
            self.canvas.update()
            self.setDirty()

    def chshapeFillColor(self):
        color = self.colorDialog.getColor(self.fillColor, u'Choose fill color',
                                          default=DEFAULT_FILL_COLOR)
        if color:
            self.canvas.selectedShape.fill_color = color
            self.canvas.update()
            self.setDirty()

    def copyShape(self):
        self.canvas.endMove(copy=True)
        self.addLabel(self.canvas.selectedShape)
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def loadPredefinedClasses(self, predefClassesFile):
        if os.path.exists(predefClassesFile) is True:
            with codecs.open(predefClassesFile, 'r', 'utf8') as f:
                for line in f:
                    line = line.strip()
                    if self.labelHist is None:
                        self.labelHist = [line]
                    else:
                        self.labelHist.append(line)

    def loadPascalXMLByFilename(self, xmlPath):
        if self.filePath is None:
            return
        if os.path.isfile(xmlPath) is False:
            return

        self.set_format(FORMAT_PASCALVOC)

        tVocParseReader = PascalVocReader(xmlPath)
        shapes = tVocParseReader.getShapes()
        self.loadLabels(shapes)
        self.canvas.verified = tVocParseReader.verified

    def loadYOLOTXTByFilename(self, txtPath):
        if self.filePath is None:  # \\
            return
        if os.path.isfile(txtPath) is False:
            return

        self.set_format(FORMAT_YOLO)

        imglabelidx = self.getImglabelidx(self.filePath)
        # if self.PPreader is None: # 第一次运行时实例化
        self.PPreader = YoloReader(txtPath, self.image)  # 从self.filePath中定位图片
        if self.PPreader.isExist(imglabelidx) is False:  # 如果不存在label直接返回
            return
        else:
            shapes = self.PPreader.getShapes(imglabelidx)  # 选择文件
            print(shapes)
            self.loadLabels(shapes)
            self.canvas.verified = self.PPreader.verified  # 这句的含义？

    def copyPreviousBoundingBoxes(self):
        currIndex = self.mImgList.index(self.filePath)
        if currIndex - 1 >= 0:
            prevFilePath = self.mImgList[currIndex - 1]
            self.showBoundingBoxFromAnnotationFile(prevFilePath)
            self.saveFile()

    def togglePaintLabelsOption(self):
        for shape in self.canvas.shapes:
            shape.paintLabel = self.displayLabelOption.isChecked()

    def toogleDrawSquare(self):
        self.canvas.setDrawingShapeToSquare(self.drawSquaresOption.isChecked())

    def additems(self, dirpath):
        # 读取和显示缩略图
        for file in self.mImgList:
            pix = QPixmap(file)
            _, filename = os.path.split(file)
            filename, _ = os.path.splitext(filename)
            # item = QListWidgetItem(QIcon(pix.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)),filename[:10])
            item = QListWidgetItem(QIcon(pix.scaled(100, 100, Qt.IgnoreAspectRatio, Qt.FastTransformation)),
                                   filename[:10])
            item.setToolTip(file)  # TODO: 每个都设置了tooltip
            self.iconlist.addItem(item)

    def getImglabelidx(self, filePath):
        # 将全路径改为半路径
        filepathsplit = filePath.split('\\')[-2:]
        return filepathsplit[0] + '/' + filepathsplit[1]

    def autoRecognition(self):
        # 直接从读入的所有文件中进行识别
        assert self.mImgList is not None
        print('Using model from ', self.model)
        if self.model == 'paddle':
            # Paddleocr目前支持中英文、英文、法语、德语、韩语、日语，可以通过修改lang参数进行切换
            # 参数依次为`ch`, `en`, `french`, `german`, `korean`, `japan`。
            ocr = PaddleOCR(use_pdserving=False, use_angle_cls=True, rec=False,
                            lang="ch")  # need to run only once to download and load model into memory
            
        uncheckedList = [i for i in self.mImgList if i not in self.fileStatedict.keys()]
        self.autoDialog = AutoDialog(parent=self, ocr=ocr, mImgList=uncheckedList, lenbar=len(uncheckedList))
        self.autoDialog.popUp()
        

        self.loadFile(self.filePath) # ADD
        self.haveAutoReced = True
        self.AutoRecognition.setEnabled(False)
        self.setDirty()


    def reRecognition(self):
        # 读入当前图片
        img = cv2.imread(self.filePath)

        # TODO: 这里需要只预测的功能，需要将移动之后的框参数传入
        # 读取 self.canvas.shapes 中的信息 然后再接一个识别模型
        # print([[(p.x(), p.y()) for p in shape.points] for shape in self.canvas.shapes]) # 得到边界框位置

        if self.canvas.shapes:
            self.result_dic = []
            rec_flag = 0
            for shape in self.canvas.shapes:
                box = [[int(p.x()), int(p.y())] for p in shape.points]
                assert len(box) == 4
                img_crop = get_rotate_crop_image(img, np.array(box, np.float32))
                result = self.ocr.ocr(img_crop, cls=True, det=False)
                # 增加一个判断条件，处理空框标注残留问题
                if result[0][0] is not '':
                    # 再将格式改回，增加box
                    result.insert(0, box)
                    print('result in reRec is ', result)

                    self.result_dic.append(result)
                    # 增加一个判断条件，检查重识别label与原label是否相同
                    if result[1][0] == shape.label:
                        print('label no change')
                    else:
                        rec_flag += 1

            # 将图片结果全部识别后再保存
            if len(self.result_dic) > 0 and rec_flag > 0:
                # self.filePath 存在
                # self.filePath = Imgpath  # 文件路径
                # 保存
                self.saveFile(mode='Auto')
                self.loadFile(self.filePath)  # 重新读入时没有读入
                self.setDirty()
            elif len(self.result_dic) == len(self.canvas.shapes) and rec_flag == 0:
                QMessageBox.information(self, "Information", "Not any change!")
            else:
                print('Can not recgonition in ', self.filePath)

        else:
            print('Draw a box!')


    def autolcm(self):
        print('autolabelchoosemodel')
        #self.listToStr([[5.0, 15.0], [23.0, 15.0], [23.0, 114.0], [5.0, 114.0]])

    def loadFilestate(self, saveDir):
        # ADD file state path： 不存在则新建 存在则读入
        # 全文件名
        self.fileStatepath = saveDir + '/fileState.txt'  # 始终出现在Paddle中
        self.fileStatedict = {}  # 保存图片状态
        if not os.path.exists(self.fileStatepath):
            f = open(self.fileStatepath, 'w', encoding='utf-8')
        # 如果存在则读取 不存在则创建
        else:
            with open(self.fileStatepath, 'r', encoding='utf-8') as f:
                states = f.readlines()
                for each in states:
                    file, state = each.split('\t')  # filename \t 后期可能会增加difficult选项
                    self.fileStatedict[file] = 1  # int(state.split('\n')[0])
        f.close()

    def saveFilestate(self):
        with open(self.fileStatepath, 'w', encoding='utf-8') as f:
            for key in self.fileStatedict:
                f.write(key + '\t')
                f.write(str(self.fileStatedict[key]) + '\n')
        f.close()

    def loadPPlabel(self, saveDir):
        # ADD file state path：
        self.PPlabelpath = saveDir + '/label.txt'  # 始终出现在Paddle中
        self.PPlabel = {}  # 保存图片状态
        if not os.path.exists(self.PPlabelpath):
            f = open(self.PPlabelpath, 'w', encoding='utf-8')
        # 如果存在则读取 不存在则创建
        else:
            with open(self.PPlabelpath, 'r', encoding='utf-8') as f:
                data = f.readlines()
                for each in data:
                    file, label = each.split('\t')  # filename \t 后期可能会增加difficult选项
                    if label:
                        label = label.replace('false', 'False')  # 对 difficult的状态替换
                        self.PPlabel[file] = eval(label)
                    else:
                        self.PPlabel[file] = []

        f.close()

    def savePPlabel(self):
        # 关闭界面后整体写入txt 按照path/img.jpg格式
        savedfile = [self.getImglabelidx(i) for i in self.fileStatedict.keys()]
        with open(self.PPlabelpath, 'w', encoding='utf-8') as f:
            for key in self.PPlabel:
                if key in savedfile:
                    f.write(key + '\t')
                    f.write(json.dumps(self.PPlabel[key], ensure_ascii=False) + '\n')
        f.close()


def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except:
        return default


def get_main_app(argv=[]):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("app"))
    # Tzutalin 201705+: Accept extra agruments to change predefined class file
    argparser = argparse.ArgumentParser()
    argparser.add_argument("image_dir", nargs="?")
    argparser.add_argument("predefined_classes_file",
                           default=os.path.join(os.path.dirname(__file__), "data", "predefined_classes.txt"),
                           nargs="?")
    argparser.add_argument("save_dir", nargs="?")
    args = argparser.parse_args(argv[1:])
    # Usage : labelImg.py image predefClassFile saveDir
    win = MainWindow(args.image_dir,
                     args.predefined_classes_file,
                     args.save_dir)
    win.show()
    return app, win


def main():
    '''construct main app and run it'''
    app, _win = get_main_app(sys.argv)
    return app.exec_()


if __name__ == '__main__':
    
    resource_file = './libs/resources.py'
    if not os.path.exists(resource_file):
        output = os.system('pyrcc5 -o libs/resources.py resources.qrc')
        assert output is 0, "operate the cmd have some problems ,please check  whether there is a in the lib " \
                            "directory resources.py "
    import libs.resources
    sys.exit(main())
