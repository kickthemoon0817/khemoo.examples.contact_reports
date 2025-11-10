from __future__ import annotations

"""
Standalone SimulationApp demo that enables the `khemoo.examples.contact_reports` extension, spawns
a ground plane plus falling shapes, and prints PhysX contact impulses when they hit the floor.
"""

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": False})

import os  # noqa: E402
import sys  # noqa: E402

EXT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if EXT_ROOT not in sys.path:
    sys.path.insert(0, EXT_ROOT)

import carb  # noqa: E402,E401
import omni.kit.app  # noqa: E402,E401
import omni.timeline  # noqa: E402,E401
import omni.usd  # noqa: E402,E401

from isaacsim.core.utils.extensions import enable_extension  # noqa: E402,E401
from khemoo.examples.contact_reports import ContactReportUI, GroundContactReporter  # noqa: E402,E401

EXTENSION_ID = "khemoo.examples.contact_reports"


def _ensure_extension():
    enable_extension(EXTENSION_ID)


def _get_stage():
    usd_context = omni.usd.get_context()
    if not usd_context.get_stage():
        usd_context.new_stage()
    return usd_context.get_stage()


def main():
    _ensure_extension()
    stage = _get_stage()
    reporter = GroundContactReporter(stage, "/World/ContactReportDemo")
    reporter.generate(cube_count=6, sphere_count=6, spawn_height=3.5, spawn_interval=2.0, batch_size=2)
    ui_panel = ContactReportUI(reporter)

    timeline = omni.timeline.get_timeline_interface()
    timeline.play()
    try:
        for _ in range(60000):
            reporter.update(timeline.get_current_time())
            simulation_app.update()
    except Exception as exc:
        print(f"[ContactReportApp] Exception during simulation loop: {exc}")
    finally:
        reporter.shutdown()
        timeline.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        carb.log_error(f"[ContactReportApp] Exception: {exc}")
    finally:
        simulation_app.close()
