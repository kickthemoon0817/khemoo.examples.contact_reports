from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

import carb
from omni.physx import get_physx_simulation_interface
from omni.physx.scripts import physicsUtils
from pxr import Gf, PhysxSchema, PhysicsSchemaTools, Sdf, UsdGeom, UsdLux, UsdPhysics


@dataclass(frozen=True)
class ContactEvent:
    actor0: str
    actor1: str
    impulse: float
    position: Gf.Vec3f


class GroundContactReporter:
    """Creates a simple arena with falling shapes and prints PhysX contact impulses."""

    def __init__(
        self,
        stage,
        root_prim_path: str = "/World/ContactReportDemo",
    ) -> None:
        self._stage = stage
        self._root_path = Sdf.Path(root_prim_path)
        self._subscription = None
        self._monitored_prim_path: Optional[Sdf.Path] = None
        self._spawn_interval = -1.0
        self._remaining_cubes = 0
        self._remaining_spheres = 0
        self._cube_index = 0
        self._sphere_index = 0
        self._spawn_height = 0.0
        self._spawn_area = 0.0
        self._batch_size = 1
        self._next_spawn_time = 0.0
        self._event_log: List[str] = []

    def generate(
        self,
        *,
        cube_count: int = 4,
        sphere_count: int = 4,
        spawn_height: float = 2.5,
        area: float = 1.5,
        random_seed: int = 7,
        spawn_interval: float = 0.5,
        batch_size: int = 2,
    ) -> None:
        """Populate the stage and start listening for contacts."""
        carb.log_info(
            f"[ContactReportDemo] Spawning {cube_count} cubes + {sphere_count} spheres at {self._root_path}"
        )
        random.seed(random_seed)
        self._setup_world()
        if not self._stage.GetPrimAtPath(self._root_path.AppendChild("Ground")):
            self._spawn_ground()
        self._subscribe_contacts()

        self._remaining_cubes = cube_count
        self._remaining_spheres = sphere_count
        self._cube_index = 0
        self._sphere_index = 0
        self._spawn_height = spawn_height
        self._spawn_area = area
        self._spawn_interval = max(spawn_interval, 0.0)
        self._batch_size = max(1, batch_size)
        self._next_spawn_time = 0.0
        self.update(0.0)

    def spawn_objects(self, cube_count: int, sphere_count: int) -> None:
        cube_count = max(0, cube_count)
        sphere_count = max(0, sphere_count)
        for _ in range(cube_count):
            path = self._root_path.AppendChild(f"Cube_{self._cube_index:03d}")
            self._create_body(path, "Cube", self._spawn_height, self._spawn_area, (0.12, 0.12, 0.12))
            self._cube_index += 1
        for _ in range(sphere_count):
            path = self._root_path.AppendChild(f"Sphere_{self._sphere_index:03d}")
            self._create_body(path, "Sphere", self._spawn_height, self._spawn_area, (0.1, 0.1, 0.1))
            self._sphere_index += 1

    def clear_spawned(self) -> None:
        root_prim = self._stage.GetPrimAtPath(self._root_path)
        if not root_prim:
            return
        to_remove = []
        for child in root_prim.GetChildren():
            name = child.GetName()
            if name.startswith("Cube_") or name.startswith("Sphere_"):
                to_remove.append(child.GetPath())
        for prim_path in to_remove:
            self._stage.RemovePrim(prim_path)
        self._remaining_cubes = 0
        self._remaining_spheres = 0
        self._cube_index = 0
        self._sphere_index = 0
        carb.log_info("[ContactReportDemo] Removed %d spawned prims" % len(to_remove))

    def _setup_world(self) -> None:
        if not self._stage.GetPrimAtPath(self._root_path):
            UsdGeom.Xform.Define(self._stage, self._root_path)
        if not self._stage.GetDefaultPrim():
            self._stage.SetDefaultPrim(self._stage.GetPrimAtPath(self._root_path))

        if not self._stage.GetPrimAtPath("/World/ContactLight"):
            light = UsdLux.DistantLight.Define(self._stage, "/World/ContactLight")
            light.CreateIntensityAttr(5000.0)
            light.CreateAngleAttr(0.6)
            light.AddTranslateOp().Set(Gf.Vec3f(2.0, -2.5, 3.0))
            light.AddOrientOp().Set(Gf.Quatf(0.9239, -0.3827, 0.0, 0.0))

    def _spawn_ground(self) -> None:
        plane_path = self._root_path.AppendChild("Ground")
        physicsUtils.add_ground_plane(
            self._stage,
            str(plane_path),
            "Z",
            size=4.0,
            position=Gf.Vec3f(0.0, 0.0, 0.0),
            color=Gf.Vec3f(0.6, 0.6, 0.65),
        )
        plane_prim = self._stage.GetPrimAtPath(str(plane_path))
        if not plane_prim or not plane_prim.IsValid():
            plane_prim = self._stage.DefinePrim(str(plane_path), "Xform")
        ground_report = PhysxSchema.PhysxContactReportAPI.Apply(plane_prim)
        ground_report.CreateThresholdAttr().Set(0.0)
        self._monitored_prim_path = plane_path

    def set_contact_target(self, prim_path: str) -> None:
        prim = self._stage.GetPrimAtPath(prim_path)
        if not prim:
            prim = self._stage.DefinePrim(prim_path, "Xform")
        contact_api = PhysxSchema.PhysxContactReportAPI.Apply(prim)
        contact_api.CreateThresholdAttr().Set(0.0)
        self._monitored_prim_path = Sdf.Path(prim_path)
        carb.log_info(f"[ContactReportDemo] Now monitoring contacts against {prim_path}")

    def set_spawn_height(self, height: float) -> None:
        self._spawn_height = max(0.0, float(height))
        carb.log_info(f"[ContactReportDemo] Spawn height set to {self._spawn_height:.2f} m")

    def update(self, current_time: float) -> None:
        if self._spawn_interval < 0.0:
            return
        if (self._remaining_cubes <= 0) and (self._remaining_spheres <= 0):
            return
        while current_time >= self._next_spawn_time - 1e-6:
            self._emit_batch()
            self._next_spawn_time += self._spawn_interval
            if (self._remaining_cubes <= 0) and (self._remaining_spheres <= 0):
                break

    def _emit_batch(self) -> None:
        cube_to_spawn = min(self._batch_size, self._remaining_cubes)
        sphere_to_spawn = min(self._batch_size, self._remaining_spheres)

        self.spawn_objects(cube_to_spawn, sphere_to_spawn)
        self._remaining_cubes -= cube_to_spawn
        self._remaining_spheres -= sphere_to_spawn

    def _create_body(
        self,
        prim_path: Sdf.Path,
        geom_type: str,
        spawn_height: float,
        area: float,
        scale_xyz,
    ) -> None:
        prim = self._stage.DefinePrim(str(prim_path), geom_type)
        xform = UsdGeom.Xformable(prim)
        xform.ClearXformOpOrder()
        xform.AddScaleOp().Set(Gf.Vec3f(*scale_xyz))
        xform.AddTranslateOp().Set(
            Gf.Vec3f(
                random.uniform(-area, area),
                random.uniform(-area, area),
                spawn_height + random.uniform(0.0, 0.5),
            )
        )

        UsdPhysics.CollisionAPI.Apply(prim).CreateCollisionEnabledAttr(True)
        PhysxSchema.PhysxCollisionAPI.Apply(prim)
        rigid_api = UsdPhysics.RigidBodyAPI.Apply(prim)
        rigid_api.CreateRigidBodyEnabledAttr(True)
        PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        PhysxSchema.PhysxContactReportAPI.Apply(prim).CreateThresholdAttr().Set(0.0)

    def _subscribe_contacts(self) -> None:
        if self._subscription:
            return
        sim_interface = get_physx_simulation_interface()
        self._subscription = sim_interface.subscribe_contact_report_events(self._on_contact_report)

    def shutdown(self) -> None:
        if self._subscription:
            self._subscription = None

    def _on_contact_report(self, contact_headers, contact_data) -> None:
        if not self._monitored_prim_path:
            return
        ground_path = str(self._monitored_prim_path)
        for header in contact_headers:
            actor0 = str(PhysicsSchemaTools.intToSdfPath(header.actor0))
            actor1 = str(PhysicsSchemaTools.intToSdfPath(header.actor1))
            if ground_path not in (actor0, actor1):
                continue
            if header.num_contact_data == 0:
                continue

            contact_range = range(header.contact_data_offset, header.contact_data_offset + header.num_contact_data)
            for idx in contact_range:
                impulse = contact_data[idx].impulse
                impulse_x, impulse_y, impulse_z = impulse.x, impulse.y, impulse.z
                impulse_amount = (impulse_x * impulse_x  + impulse_y * impulse_y + impulse_z * impulse_z) ** 0.5
                event = ContactEvent(
                    actor0=actor0,
                    actor1=actor1,
                    impulse=impulse_amount,
                    position=contact_data[idx].position,
                )
                self._print_event(event)

    def _print_event(self, event: ContactEvent) -> None:
        message = (
            "[ContactReportDemo] contact: actors=(%s, %s) | impulse=%.4f | pos=(%.3f, %.3f, %.3f)"
            % (
                event.actor0,
                event.actor1,
                event.impulse,
                event.position[0],
                event.position[1],
                event.position[2],
            )
        )
        carb.log_info(message)
        self._event_log.append(message)

    def get_recent_log(self, limit: int = 20) -> List[str]:
        return self._event_log[-limit:]
