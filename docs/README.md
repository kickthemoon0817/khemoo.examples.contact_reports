# khemoo.examples.contact_reports

Spawns a PhysX scene with a thin rigid cube floor plus randomly placed cubes and spheres that fall under gravity.
The demo enables `PhysxContactReportAPI` on selected prims (ground or custom) and subscribes to the PhysX contact stream,
printing each contact impulse (magnitude and position) to the console.

## Using the extension

### In an existing Kit session

```python
import omni.usd
from isaacsim.core.utils.extensions import enable_extension

enable_extension("khemoo.examples.contact_reports")

from khemoo.examples.contact_reports import ContactReportUI, ContactReporter

stage = omni.usd.get_context().get_stage()
reporter = ContactReporter(stage, "/World/ContactReport")
reporter.generate(cube_count=6, sphere_count=4, spawn_height=3.0)
ui_panel = ContactReportUI(reporter)
```

Press play (space bar) and watch the console for `[ContactReport]` logs as shapes hit monitored prims. Objects are
dropped in timed batches following the simulation timeline, so you can see impulses for each wave of falling bodies.
Use the UI to change the monitored prim(s) (any rigid body path, comma separated), tweak spawn height, spawn additional cubes/spheres,
clear spawned objects, or review the contact log history.

### Standalone SimulationApp

Run `python extsUser/khemoo.examples.contact_reports/khemoo/examples/contact_reports/examples/contact_report_app.py`
to boot a SimulationApp, spawn the scene, and interact with the UI panel to change the monitored prims, adjust spawn height,
spawn additional objects, or remove existing ones.
