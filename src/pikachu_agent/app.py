from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .town import AgentTownWindow
from .ui import PikachuWindow
from .portal import TownPortal
from .communication import DragoniteMailWindow
from .project_center import ProjectCenterWindow
from .music import MeloettaMusicWindow


class AppController:
    def __init__(self, application: QApplication, project_root: Path):
        self.application = application
        self.project_root = project_root
        self.town = AgentTownWindow(project_root)
        self.companion = PikachuWindow(project_root)
        self.dragonite = DragoniteMailWindow(project_root)
        self.porygon = ProjectCenterWindow(project_root)
        self.meloetta = MeloettaMusicWindow(project_root)
        self.portal = TownPortal(project_root)
        self.town.summon_requested.connect(self.summon)
        self.companion.return_home.connect(self.show_town)
        self.dragonite.return_home.connect(self.show_town)
        self.porygon.return_home.connect(self.show_town)
        self.meloetta.return_home.connect(self.show_town)
        self.portal.activated.connect(self.show_town)
        self.tray = self._create_tray()

    def _create_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(QIcon(str(self.project_root / "assets" / "pikachu.png")), self.application)
        tray.setToolTip("Agent Town")
        menu = QMenu()
        town_action = QAction("打開 Agent Town", menu)
        town_action.triggered.connect(self.show_town)
        summon_action = QAction("召喚皮卡丘", menu)
        summon_action.triggered.connect(lambda: self.summon("pikachu"))
        dragonite_action = QAction("召喚快龍", menu)
        dragonite_action.triggered.connect(lambda: self.summon("dragonite"))
        porygon_action = QAction("召喚多邊獸", menu)
        porygon_action.triggered.connect(lambda: self.summon("porygon"))
        meloetta_action = QAction("召喚美洛耶塔", menu)
        meloetta_action.triggered.connect(lambda: self.summon("meloetta"))
        quit_action = QAction("離開", menu)
        quit_action.triggered.connect(self.application.quit)
        menu.addAction(town_action)
        menu.addAction(summon_action)
        menu.addAction(dragonite_action)
        menu.addAction(porygon_action)
        menu.addAction(meloetta_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        return tray

    def start(self) -> None:
        screen = self.application.primaryScreen().geometry()
        self.portal.place_on_screen(screen)
        self.portal.show()

    def show_town(self) -> None:
        self.companion.hide()
        self.dragonite.hide()
        self.porygon.hide()
        self.meloetta.hide()
        self.town.show()
        self.town.raise_()
        self.town.activateWindow()

    def summon(self, agent_id: str) -> None:
        if agent_id == "meloetta":
            self.town.hide()
            self.companion.hide()
            self.dragonite.hide()
            self.porygon.hide()
            self.meloetta.show()
            self.meloetta.raise_()
            self.meloetta.activateWindow()
            return
        if agent_id == "porygon":
            self.town.hide()
            self.companion.hide()
            self.dragonite.hide()
            self.meloetta.hide()
            self.porygon.refresh()
            self.porygon.show()
            self.porygon.raise_()
            self.porygon.activateWindow()
            return
        if agent_id == "dragonite":
            self.town.hide()
            self.companion.hide()
            self.porygon.hide()
            self.meloetta.hide()
            self.dragonite.show()
            self.dragonite.raise_()
            self.dragonite.activateWindow()
            return
        if agent_id != "pikachu":
            return
        self.town.hide()
        self.dragonite.hide()
        self.porygon.hide()
        self.meloetta.hide()
        screen = self.application.primaryScreen().availableGeometry()
        self.companion.adjustSize()
        self.companion.move(
            screen.right() - self.companion.width() - 28,
            screen.bottom() - self.companion.height() - 24,
        )
        self.companion.show()
        self.companion.raise_()
        self.companion.activateWindow()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick}:
            self.show_town()


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    application = QApplication(sys.argv)
    application.setApplicationName("Agent Town")
    application.setWindowIcon(QIcon(str(project_root / "assets" / "pikachu.png")))
    application.setQuitOnLastWindowClosed(False)
    controller = AppController(application, project_root)
    controller.start()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
