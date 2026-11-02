#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Editor visual do mapa mental (arrastar/renomear).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QSplitter, QVBoxLayout, QWidget, QInputDialog,
)


class MindmapEditorView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.info = QLabel("Editor visual: arrastar e renomear ramos/itens do mapa mental.")
        self.info.setStyleSheet("color:#5b6673;")
        layout.addWidget(self.info)

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        l_layout = QVBoxLayout(left)
        l_layout.addWidget(QLabel("Ramos"))
        self.branches = QListWidget()
        l_layout.addWidget(self.branches)
        b_row = QHBoxLayout()
        self.btn_rename_branch = QPushButton("Renomear ramo")
        self.btn_add_branch = QPushButton("Adicionar ramo")
        self.btn_remove_branch = QPushButton("Remover ramo")
        b_row.addWidget(self.btn_rename_branch)
        b_row.addWidget(self.btn_add_branch)
        b_row.addWidget(self.btn_remove_branch)
        l_layout.addLayout(b_row)
        splitter.addWidget(left)

        right = QWidget()
        r_layout = QVBoxLayout(right)
        r_layout.addWidget(QLabel("Itens"))
        self.items = QListWidget()
        self.items.setDragDropMode(QListWidget.InternalMove)
        self.items.setDefaultDropAction(Qt.MoveAction)
        r_layout.addWidget(self.items)
        i_row = QHBoxLayout()
        self.btn_rename_item = QPushButton("Renomear item")
        self.btn_add_item = QPushButton("Adicionar item")
        self.btn_remove_item = QPushButton("Remover item")
        i_row.addWidget(self.btn_rename_item)
        i_row.addWidget(self.btn_add_item)
        i_row.addWidget(self.btn_remove_item)
        r_layout.addLayout(i_row)
        splitter.addWidget(right)

        layout.addWidget(splitter)

        self.btn_rename_branch.clicked.connect(self._rename_branch)
        self.btn_add_branch.clicked.connect(self._add_branch)
        self.btn_remove_branch.clicked.connect(self._remove_branch)
        self.btn_rename_item.clicked.connect(self._rename_item)
        self.btn_add_item.clicked.connect(self._add_item)
        self.btn_remove_item.clicked.connect(self._remove_item)
        self.branches.currentRowChanged.connect(self._load_items)

        self._mindmap = {"title": "", "branches": []}

    def load_mindmap(self, mindmap: dict):
        self._mindmap = dict(mindmap or {})
        if "branches" not in self._mindmap:
            self._mindmap["branches"] = []
        self.branches.clear()
        for branch in self._mindmap["branches"]:
            self.branches.addItem(branch.get("name", ""))
        if self.branches.count():
            self.branches.setCurrentRow(0)

    def get_mindmap(self):
        # Atualiza com ordem arrastada
        if self.branches.currentRow() >= 0:
            row = self.branches.currentRow()
            branches = self._mindmap.get("branches", [])
            if row < len(branches):
                items = []
                for i in range(self.items.count()):
                    items.append({"name": self.items.item(i).text(), "weight": branches[row].get("children", [])[i].get("weight", 0) if i < len(branches[row].get("children", [])) else 0})
                branches[row]["children"] = items
        return self._mindmap

    def _load_items(self, row):
        self.items.clear()
        branches = self._mindmap.get("branches", [])
        if row < 0 or row >= len(branches):
            return
        for child in branches[row].get("children", []):
            self.items.addItem(child.get("name", ""))

    def _rename_branch(self):
        row = self.branches.currentRow()
        if row < 0:
            return
        item = self.branches.item(row)
        new, ok = QInputDialog.getText(self, "Renomear ramo", "Nome:", text=item.text())
        if ok and new.strip():
            item.setText(new.strip())
            self._mindmap["branches"][row]["name"] = new.strip()

    def _add_branch(self):
        name, ok = QInputDialog.getText(self, "Adicionar ramo", "Nome:")
        if ok and name.strip():
            self._mindmap.setdefault("branches", []).append({"name": name.strip(), "children": []})
            self.branches.addItem(name.strip())

    def _remove_branch(self):
        row = self.branches.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, "Remover ramo", "Remover este ramo?") != QMessageBox.Yes:
            return
        self.branches.takeItem(row)
        self._mindmap["branches"].pop(row)
        self.items.clear()

    def _rename_item(self):
        row = self.items.currentRow()
        brow = self.branches.currentRow()
        if row < 0 or brow < 0:
            return
        item = self.items.item(row)
        new, ok = QInputDialog.getText(self, "Renomear item", "Nome:", text=item.text())
        if ok and new.strip():
            item.setText(new.strip())
            children = self._mindmap["branches"][brow].setdefault("children", [])
            if row < len(children):
                children[row]["name"] = new.strip()

    def _add_item(self):
        brow = self.branches.currentRow()
        if brow < 0:
            return
        name, ok = QInputDialog.getText(self, "Adicionar item", "Nome:")
        if ok and name.strip():
            self.items.addItem(name.strip())
            self._mindmap["branches"][brow].setdefault("children", []).append({"name": name.strip(), "weight": 0})

    def _remove_item(self):
        row = self.items.currentRow()
        brow = self.branches.currentRow()
        if row < 0 or brow < 0:
            return
        if QMessageBox.question(self, "Remover item", "Remover este item?") != QMessageBox.Yes:
            return
        self.items.takeItem(row)
        children = self._mindmap["branches"][brow].setdefault("children", [])
        if row < len(children):
            children.pop(row)
