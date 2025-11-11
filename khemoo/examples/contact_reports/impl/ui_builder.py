from __future__ import annotations

from typing import List, Optional

import carb
import omni.ui as ui

DEFAULT_TARGET_PATH = "/World/ContactReport/Ground"


class ContactReportUI:
    """Simple standalone window (used by the SimulationApp example)."""

    def __init__(self, reporter, window_title: str = "Contact Report Controls"):
        self._reporter = reporter
        self._window = ui.Window(window_title, width=320, height=200)
        self._target_model = ui.SimpleStringModel(DEFAULT_TARGET_PATH)
        self._cube_model = ui.SimpleIntModel(2)
        self._sphere_model = ui.SimpleIntModel(2)
        self._height_model = ui.SimpleFloatModel(3.0)
        with self._window.frame:
            ContactReportUIBuilder.build_layout(
                self._reporter,
                self._target_model,
                self._cube_model,
                self._sphere_model,
                self._height_model,
            )


class ContactReportUIBuilder:
    """Reusable UI builder that Isaac Sim's extension system hooks into."""

    def __init__(self) -> None:
        self.frames: List[ui.AbstractItem] = []
        self.wrapped_ui_elements: List[ui.Widget] = []
        self._reporter = None
        self._target_model = ui.SimpleStringModel(DEFAULT_TARGET_PATH)
        self._cube_model = ui.SimpleIntModel(2)
        self._sphere_model = ui.SimpleIntModel(2)
        self._height_model = ui.SimpleFloatModel(3.0)

    def bind_reporter(self, reporter) -> None:
        self._reporter = reporter

    def on_menu_callback(self) -> None:
        self._reset_models()

    def on_stage_event(self, event) -> None:
        # Nothing special for now; placeholder for future use.
        _ = event

    def cleanup(self) -> None:
        self.frames.clear()
        self.wrapped_ui_elements.clear()
        self._reporter = None

    def build_ui(self) -> None:
        ContactReportUIBuilder.build_layout(
            self._reporter,
            self._target_model,
            self._cube_model,
            self._sphere_model,
            self._height_model,
        )

    @staticmethod
    def build_layout(reporter, target_model, cube_model, sphere_model, height_model):
        with ui.VStack(spacing=6, height=0):
            ui.Label("Contact target prim path(s) (comma separated)", height=0)
            ui.StringField(model=target_model)
            ui.Button("Set Target", clicked_fn=lambda: ContactReportUIBuilder._apply_target(reporter, target_model))

            ui.Spacer(height=8)
            ui.Label("Spawn batch", height=0)
            with ui.HStack(spacing=4, height=0):
                ui.Label("Cubes")
                ui.IntField(model=cube_model, min=0)
                ui.Label("Spheres")
                ui.IntField(model=sphere_model, min=0)
            ui.Button(
                "Spawn Objects",
                clicked_fn=lambda: ContactReportUIBuilder._spawn_objects(reporter, cube_model, sphere_model),
            )
            ui.Button(
                "Clear Spawned Objects",
                clicked_fn=lambda: ContactReportUIBuilder._clear_spawned(reporter),
                height=0,
            )
            ui.Spacer(height=8)
            with ui.HStack(spacing=4, height=0):
                ui.Label("Spawn Height (m)")
                ui.FloatField(model=height_model, min=0.1)
            ui.Button(
                "Apply Spawn Height",
                clicked_fn=lambda: ContactReportUIBuilder._apply_height(reporter, height_model),
                height=0,
            )
            ui.Spacer(height=8)
            ui.Label("History", height=0)
            log_frame = ui.ScrollingFrame(height=140)
            with log_frame:
                with ui.VStack(height=0):
                    log_source = reporter.get_recent_log() if reporter else []
                    for line in log_source:
                        ui.Label(line, height=0)

    def _reset_models(self) -> None:
        self._target_model.set_value(DEFAULT_TARGET_PATH)
        self._cube_model.set_value(2)
        self._sphere_model.set_value(2)
        self._height_model.set_value(3.0)

    @staticmethod
    def _apply_target(reporter, target_model) -> None:
        if reporter is None:
            carb.log_warn("[ContactReportUI] Reporter not ready yet.")
            return
        raw_value = target_model.get_value_as_string()
        targets = ContactReportUIBuilder._parse_target_entries(raw_value)
        if not targets:
            carb.log_warn("[ContactReportUI] Target path list is empty.")
            return
        reporter.set_contact_targets(targets)

    @staticmethod
    def _spawn_objects(reporter, cube_model, sphere_model) -> None:
        if reporter is None:
            carb.log_warn("[ContactReportUI] Reporter not ready yet.")
            return
        cubes = max(0, int(cube_model.get_value_as_int()))
        spheres = max(0, int(sphere_model.get_value_as_int()))
        if cubes == 0 and spheres == 0:
            carb.log_warn("[ContactReportUI] Add at least one object to spawn.")
            return
        reporter.spawn_objects(cubes, spheres)

    @staticmethod
    def _clear_spawned(reporter) -> None:
        if reporter is None:
            carb.log_warn("[ContactReportUI] Reporter not ready yet.")
            return
        reporter.clear_spawned()

    @staticmethod
    def _apply_height(reporter, height_model) -> None:
        if reporter is None:
            carb.log_warn("[ContactReportUI] Reporter not ready yet.")
            return
        reporter.set_spawn_height(height_model.get_value_as_float())
        carb.log_info(
            "[ContactReportUI] Spawn height set to %.2f m" % height_model.get_value_as_float()
        )

    @staticmethod
    def _parse_target_entries(raw_value: str) -> List[str]:
        if not raw_value:
            return []
        normalized = raw_value.replace("\n", ",").split(",")
        return [entry.strip() for entry in normalized if entry.strip()]
