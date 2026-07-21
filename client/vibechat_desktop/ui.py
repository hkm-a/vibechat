"""VibeChat 原生桌面 UI（PySide6，非浏览器）。"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QStackedWidget,
    QFrame,
)

from .tinode_bridge import TinodeBridge

STYLE = """
QWidget { background: #0f1117; color: #e8ecf5; font-size: 14px; }
QLineEdit, QTextEdit, QListWidget {
  background: #1e2330; border: 1px solid #2a3142; border-radius: 8px; padding: 8px;
  selection-background-color: #6366f1;
}
QPushButton {
  background: #2a3150; border: 1px solid #3b4270; border-radius: 8px; padding: 8px 14px;
}
QPushButton:hover { background: #343c64; }
QPushButton#primary {
  background: #6366f1; border: none; color: white; font-weight: 600;
}
QPushButton#primary:hover { background: #818cf8; }
QListWidget::item { padding: 10px; border-bottom: 1px solid #2a3142; }
QListWidget::item:selected { background: #2a3150; }
QLabel#muted { color: #8b93a7; font-size: 12px; }
QLabel#title { font-size: 18px; font-weight: 700; }
QFrame#card {
  background: #171a22; border: 1px solid #2a3142; border-radius: 14px;
}
"""


class LoginPage(QWidget):
    def __init__(self, on_login) -> None:
        super().__init__()
        self.on_login = on_login
        card = QFrame()
        card.setObjectName("card")
        form = QFormLayout(card)
        self.host = QLineEdit("localhost:6060")
        self.user = QLineEdit()
        self.user.setPlaceholderText("你的真人账号")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.ssl = QCheckBox("使用 wss")
        self.err = QLabel("")
        self.err.setStyleSheet("color:#f87171;")
        btn = QPushButton("登录")
        btn.setObjectName("primary")
        btn.clicked.connect(self._submit)
        title = QLabel("VibeChat Desktop")
        title.setObjectName("title")
        hint = QLabel("原生客户端 · 直连 Tinode WebSocket（非网页）\nNPC 号请勿登录；验证码注册用网页 123456")
        hint.setObjectName("muted")
        form.addRow(title)
        form.addRow(hint)
        form.addRow("服务器", self.host)
        form.addRow("用户名", self.user)
        form.addRow("密码", self.password)
        form.addRow("", self.ssl)
        form.addRow(btn)
        form.addRow(self.err)
        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(2)
        card.setFixedWidth(420)

    def _submit(self) -> None:
        self.err.setText("")
        self.on_login(
            self.host.text().strip(),
            self.user.text().strip(),
            self.password.text(),
            self.ssl.isChecked(),
        )

    def set_error(self, msg: str) -> None:
        self.err.setText(msg)

    def load_settings(self, s: QSettings) -> None:
        self.host.setText(s.value("host", "localhost:6060"))
        self.user.setText(s.value("user", ""))
        self.ssl.setChecked(s.value("ssl", "0") == "1")

    def save_settings(self, s: QSettings) -> None:
        s.setValue("host", self.host.text().strip())
        s.setValue("user", self.user.text().strip())
        s.setValue("ssl", "1" if self.ssl.isChecked() else "0")


class SearchDialog(QDialog):
    def __init__(self, bridge: TinodeBridge, title: str, multi: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self.multi = multi
        self.selected: dict[str, str] = {}  # user -> fn
        self.setWindowTitle(title)
        self.resize(480, 520)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("角色名 / 用户名，如 卡芙卡 或 hsr_kafka")
        btn = QPushButton("搜索")
        btn.setObjectName("primary")
        btn.clicked.connect(self._do_search)
        row.addWidget(self.query)
        row.addWidget(btn)
        layout.addLayout(row)
        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(self._pick_item)
        layout.addWidget(self.results)
        if multi:
            self.chips = QLabel("已选：无")
            self.chips.setObjectName("muted")
            self.chips.setWordWrap(True)
            layout.addWidget(self.chips)
            self.name = QLineEdit()
            self.name.setPlaceholderText("群名称")
            layout.addWidget(self.name)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._conn = bridge.search_results.connect(self._on_results)

    def _do_search(self) -> None:
        self.bridge.search(self.query.text())

    def _on_results(self, results: list) -> None:
        self.results.clear()
        for r in results:
            item = QListWidgetItem(f"{r['fn']}  ({r['user']})")
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.results.addItem(item)
        if not results:
            self.results.addItem(QListWidgetItem("没有结果（等 NPC 上线后再搜）"))

    def _pick_item(self, item: QListWidgetItem) -> None:
        r = item.data(Qt.ItemDataRole.UserRole)
        if not r:
            return
        if self.multi:
            self.selected[r["user"]] = r["fn"]
            self.chips.setText("已选：" + "、".join(self.selected.values()))
        else:
            self.selected = {r["user"]: r["fn"]}
            self.accept()

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            self.bridge.search_results.disconnect(self._on_results)
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)


class MainPage(QWidget):
    def __init__(self, bridge: TinodeBridge, on_logout) -> None:
        super().__init__()
        self.bridge = bridge
        self.on_logout = on_logout
        self.current_topic: str | None = None

        root = QHBoxLayout(self)
        splitter = QSplitter()
        root.addWidget(splitter)

        # 左侧
        left = QWidget()
        left_l = QVBoxLayout(left)
        head = QHBoxLayout()
        self.me_label = QLabel("—")
        self.me_label.setObjectName("title")
        logout_btn = QPushButton("退出")
        logout_btn.clicked.connect(on_logout)
        head.addWidget(self.me_label, 1)
        head.addWidget(logout_btn)
        left_l.addLayout(head)
        actions = QHBoxLayout()
        dm_btn = QPushButton("找人")
        grp_btn = QPushButton("建群")
        grp_btn.setObjectName("primary")
        dm_btn.clicked.connect(self._find_dm)
        grp_btn.clicked.connect(self._new_group)
        actions.addWidget(dm_btn)
        actions.addWidget(grp_btn)
        left_l.addLayout(actions)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("过滤会话…")
        self.filter.textChanged.connect(self.refresh_topics)
        left_l.addWidget(self.filter)
        self.topic_list = QListWidget()
        self.topic_list.itemClicked.connect(self._topic_clicked)
        left_l.addWidget(self.topic_list)
        splitter.addWidget(left)

        # 右侧
        right = QWidget()
        right_l = QVBoxLayout(right)
        top = QHBoxLayout()
        self.topic_title = QLabel("选择一个会话")
        self.topic_title.setObjectName("title")
        self.members_btn = QPushButton("成员")
        self.members_btn.clicked.connect(self._manage_members)
        self.members_btn.setEnabled(False)
        top.addWidget(self.topic_title, 1)
        top.addWidget(self.members_btn)
        right_l.addLayout(top)
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        right_l.addWidget(self.chat, 1)
        compose = QHBoxLayout()
        self.input = QTextEdit()
        self.input.setFixedHeight(72)
        self.input.setPlaceholderText("输入消息，Ctrl+Enter 发送")
        send = QPushButton("发送")
        send.setObjectName("primary")
        send.clicked.connect(self._send)
        compose.addWidget(self.input, 1)
        compose.addWidget(send)
        right_l.addLayout(compose)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        right_l.addWidget(self.status)
        splitter.addWidget(right)
        splitter.setSizes([300, 800])

        bridge.topics_changed.connect(self.refresh_topics)
        bridge.messages_changed.connect(self._on_messages)
        bridge.status.connect(self.status.setText)
        bridge.error.connect(self._on_error)
        bridge.group_created.connect(self._on_group_created)
        bridge.signed_in.connect(self._on_signed_in)

    def _on_signed_in(self, user_id: str, name: str) -> None:
        self.me_label.setText(name or user_id)

    def _on_error(self, msg: str) -> None:
        self.status.setText(msg)
        QMessageBox.warning(self, "提示", msg)

    def refresh_topics(self) -> None:
        filt = self.filter.text().strip().lower()
        self.topic_list.clear()
        items = sorted(self.bridge.topics.values(), key=lambda t: t.seq, reverse=True)
        for t in items:
            if t.topic in ("me", "fnd"):
                continue
            title = t.title or t.topic
            if filt and filt not in title.lower() and filt not in t.topic.lower():
                continue
            kind = "群" if t.is_group else "私"
            item = QListWidgetItem(f"[{kind}] {title}\n{t.last[:40]}")
            item.setData(Qt.ItemDataRole.UserRole, t.topic)
            self.topic_list.addItem(item)

    def _topic_clicked(self, item: QListWidgetItem) -> None:
        topic = item.data(Qt.ItemDataRole.UserRole)
        if not topic:
            return
        self.current_topic = topic
        info = self.bridge.topics.get(topic)
        self.topic_title.setText((info.title if info else None) or topic)
        self.members_btn.setEnabled(str(topic).startswith("grp"))
        self.bridge.open_topic(topic)
        self._render_messages(topic)

    def _on_messages(self, topic: str) -> None:
        if topic == self.current_topic:
            self._render_messages(topic)
        self.refresh_topics()

    def _render_messages(self, topic: str) -> None:
        self.chat.clear()
        for m in self.bridge.messages.get(topic, []):
            who = "我" if m.get("me") else (m.get("from") or "?")
            text = m.get("content") or ""
            self.chat.append(f"<b style='color:#a5b4fc'>{who}</b><br/>{self._esc(text)}<br/>")

    @staticmethod
    def _esc(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )

    def _send(self) -> None:
        if not self.current_topic:
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.bridge.send_text(self.current_topic, text)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._send()
            return
        super().keyPressEvent(event)

    def _find_dm(self) -> None:
        dlg = SearchDialog(self.bridge, "找人聊天", multi=False, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected:
            user, fn = next(iter(dlg.selected.items()))
            self.bridge._ensure_topic(user, title=fn, is_group=False)
            self.current_topic = user
            self.topic_title.setText(fn)
            self.members_btn.setEnabled(False)
            self.bridge.open_topic(user)
            self.refresh_topics()

    def _new_group(self) -> None:
        dlg = SearchDialog(self.bridge, "新建群组（搜索后双击添加成员）", multi=True, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = dlg.name.text().strip()
            if not name:
                QMessageBox.warning(self, "提示", "请填写群名称")
                return
            if not dlg.selected:
                QMessageBox.warning(self, "提示", "请双击搜索结果添加成员")
                return
            self.bridge.create_group(name, list(dlg.selected.keys()))

    def _on_group_created(self, topic: str) -> None:
        self.current_topic = topic
        info = self.bridge.topics.get(topic)
        self.topic_title.setText((info.title if info else None) or topic)
        self.members_btn.setEnabled(True)
        self.bridge.open_topic(topic)
        self.refresh_topics()

    def _manage_members(self) -> None:
        if not self.current_topic or not str(self.current_topic).startswith("grp"):
            return
        topic = self.current_topic
        self.bridge.refresh_members(topic)
        info = self.bridge.topics.get(topic)
        members = (info.members if info else []) or []
        lines = []
        for m in members:
            user = m.get("user")
            fn = ((m.get("public") or {}).get("fn")) or user
            lines.append(f"{fn} ({user})")
        text = "\n".join(lines) if lines else "（暂无成员信息，稍后点成员刷新）"
        box = QMessageBox(self)
        box.setWindowTitle("群成员")
        box.setText(text)
        add_btn = box.addButton("添加成员", QMessageBox.ButtonRole.ActionRole)
        box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is add_btn:
            dlg = SearchDialog(self.bridge, "添加成员（双击选择）", multi=False, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected:
                user = next(iter(dlg.selected.keys()))
                self.bridge.add_member(topic, user)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VibeChat Desktop")
        self.resize(1100, 720)
        self.settings = QSettings("VibeChat", "Desktop")
        self.bridge = TinodeBridge()
        self.bridge.start_thread()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.login_page = LoginPage(self._do_login)
        self.main_page = MainPage(self.bridge, self._logout)
        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.main_page)
        self.login_page.load_settings(self.settings)

        self.bridge.signed_in.connect(self._on_signed_in)
        self.bridge.error.connect(self._on_login_error)
        self.bridge.signed_out.connect(lambda r: self.statusBar().showMessage(f"断开: {r}"))

    def _do_login(self, host: str, user: str, password: str, ssl: bool) -> None:
        if not host or not user or not password:
            self.login_page.set_error("请填写完整")
            return
        self.login_page.set_error("登录中…")
        self.login_page.save_settings(self.settings)
        self.bridge.login(host, user, password, ssl=ssl)

    def _on_signed_in(self, user_id: str, name: str) -> None:
        self.login_page.set_error("")
        self.stack.setCurrentWidget(self.main_page)
        self.statusBar().showMessage(f"已登录 {user_id}")

    def _on_login_error(self, msg: str) -> None:
        if self.stack.currentWidget() is self.login_page:
            self.login_page.set_error(msg)

    def _logout(self) -> None:
        self.bridge.logout()
        self.stack.setCurrentWidget(self.login_page)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.bridge.stop()
        super().closeEvent(event)


def run() -> None:
    import sys

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())