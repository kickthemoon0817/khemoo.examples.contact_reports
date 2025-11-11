from __future__ import annotations

from typing import Optional

import carb
import omni.ext
import omni.ui as ui
import omni.usd
from omni.kit.menu.utils import MenuItemDescription, add_menu_items, remove_menu_items
from omni.physx.bindings import _physx as physx_settings

from .contact_report import ContactReporter
from .ui_builder import ContactReportUIBuilder

EXTENSION_TITLE = "Contact Report"


class ContactReportsExtension(omni.ext.IExt):
    """Extension entry-point that wires the ContactReporter into an Omni.UI panel."""

    def __init__(self) -> None:
        super().__init__()
        self._ext_id: Optional[str] = None
        self._settings = carb.settings.get_settings()
        self._usd_context = None
        self._window: Optional[ui.Window] = None
        self._reporter: Optional[ContactReporter] = None
        self._ui_builder = ContactReportUIBuilder()
        self._menu_items = []
        self._stage_event_sub = None

    def on_startup(self, ext_id: str) -> None:
        self._ext_id = ext_id
        carb.log_info(f"{EXTENSION_TITLE} ({ext_id}) loaded.")
        self._settings.set(physx_settings.SETTING_UPDATE_PARTICLES_TO_USD, True)
        self._settings.set(physx_settings.SETTING_UPDATE_VELOCITIES_TO_USD, True)

        self._usd_context = omni.usd.get_context()
        self._window = ui.Window(EXTENSION_TITLE, width=360, height=320, visible=False)
        self._window.set_visibility_changed_fn(self._on_window)

        self._menu_items = [MenuItemDescription(name=EXTENSION_TITLE, onclick_fn=self._menu_callback)]
        add_menu_items(self._menu_items, "Examples")

    def on_shutdown(self) -> None:
        carb.log_info(f"{EXTENSION_TITLE} shutting down.")
        if self._reporter:
            self._reporter.shutdown()
            self._reporter = None
        self._ui_builder.cleanup()
        if self._stage_event_sub:
            self._stage_event_sub = None
        if self._window:
            self._window.destroy()
            self._window = None
        if self._menu_items:
            remove_menu_items(self._menu_items, "Examples")
            self._menu_items = []
        self._usd_context = None
        self._ext_id = None

    def _ensure_reporter(self):
        if not self._usd_context:
            return
        stage = self._usd_context.get_stage()
        if not stage:
            carb.log_info(f"[{EXTENSION_TITLE}] No stage detected, creating a new stage.")
            self._usd_context.new_stage()
            stage = self._usd_context.get_stage()
        if not stage:
            carb.log_error(f"[{EXTENSION_TITLE}] Unable to obtain a USD stage.")
            return
        if self._reporter is None:
            self._reporter = ContactReporter(stage, "/World/ContactReport")
            # Defer spawning until user requests it; just ensure contact subscription is ready.
            self._reporter.generate(cube_count=0, sphere_count=0, spawn_height=3.0, spawn_interval=1.0, batch_size=1)
        self._ui_builder.bind_reporter(self._reporter)

    def _on_window(self, _visible: bool) -> None:
        if not self._window:
            return
        if self._window.visible:
            self._ensure_reporter()
            events = self._usd_context.get_stage_event_stream()
            self._stage_event_sub = events.create_subscription_to_pop(self._on_stage_event)
            self._build_ui()
            self._ui_builder.on_menu_callback()
        else:
            if self._stage_event_sub:
                self._stage_event_sub = None
            self._ui_builder.cleanup()

    def _build_extension_ui(self):
        self._ui_builder.build_ui()

    def _build_ui(self):
        if not self._window:
            return
        with self._window.frame:
            with ui.VStack(spacing=5, height=0):
                self._build_extension_ui()

    def _menu_callback(self):
        if not self._window:
            return
        self._window.visible = not self._window.visible
        self._ui_builder.on_menu_callback()

    def _on_stage_event(self, event):
        if event.type in (int(omni.usd.StageEventType.CLOSED), int(omni.usd.StageEventType.OPENED)):
            if self._reporter:
                self._reporter.shutdown()
                self._reporter = None
            self._ui_builder.cleanup()
        self._ui_builder.on_stage_event(event)
