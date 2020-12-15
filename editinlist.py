import sys
from PyQt5 import QtWidgets
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

class EditInList(QListWidget):
    def __init__(self):
        super(EditInList,self).__init__()
        # doubleclick to edit
        self.edited_item = self.currentItem()
        self.close_flag = True
        self.clicked.connect(self.item_clicked)  

    def item_clicked(self, modelindex: QModelIndex) -> None:
        item = self.item(modelindex.row())
        self.edited_item = item
        self.openPersistentEditor(item)
        self.editItem(item)