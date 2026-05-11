"""Generate a cut-list CSV from KitchenSpecs with panel calculations."""
import csv
import io
from app.models.schemas import KitchenSpecs


_PANEL_THICKNESS_MM = 18.0


def generate_csv(specs: KitchenSpecs, project_name: str = "kitchen") -> tuple[str, str]:
    """Return (csv_content, filename) from KitchenSpecs."""
    panels = _calculate_panels(specs)
    filename = f"{project_name.lower().replace(' ', '_')}_cut_list.csv"
    csv_content = _write_csv(panels)
    return csv_content, filename


def _calculate_panels(specs: KitchenSpecs) -> list[dict]:
    panels: list[dict] = []
    w = specs.width_cm or 0
    d = specs.depth_cm or 0
    h = specs.height_cm or 0
    t = _PANEL_THICKNESS_MM / 10  # cm

    if w and d and h:
        panels += [
            {"part": "Left Side Panel", "qty": 1, "width_cm": d, "height_cm": h, "thickness_mm": _PANEL_THICKNESS_MM, "material": specs.material or "MDF"},
            {"part": "Right Side Panel", "qty": 1, "width_cm": d, "height_cm": h, "thickness_mm": _PANEL_THICKNESS_MM, "material": specs.material or "MDF"},
            {"part": "Top Panel", "qty": 1, "width_cm": w - 2 * t, "height_cm": d, "thickness_mm": _PANEL_THICKNESS_MM, "material": specs.material or "MDF"},
            {"part": "Bottom Panel", "qty": 1, "width_cm": w - 2 * t, "height_cm": d, "thickness_mm": _PANEL_THICKNESS_MM, "material": specs.material or "MDF"},
            {"part": "Back Panel", "qty": 1, "width_cm": w - 2 * t, "height_cm": h - 2 * t, "thickness_mm": 6.0, "material": "HDF"},
        ]

    num_doors = specs.num_doors or 0
    if num_doors > 0 and w and h:
        door_w = round((w / num_doors) - 0.2, 2)
        door_h = round(h * 0.7, 2)
        panels.append({"part": "Door", "qty": num_doors, "width_cm": door_w, "height_cm": door_h, "thickness_mm": _PANEL_THICKNESS_MM, "material": specs.material or "MDF"})

    num_drawers = specs.num_drawers or 0
    if num_drawers > 0 and w:
        drawer_w = round((w / max(num_drawers, 1)) - 0.4, 2)
        panels.append({"part": "Drawer Front", "qty": num_drawers, "width_cm": drawer_w, "height_cm": 15.0, "thickness_mm": _PANEL_THICKNESS_MM, "material": specs.material or "MDF"})
        panels.append({"part": "Drawer Box Side", "qty": num_drawers * 2, "width_cm": d - 5, "height_cm": 12.0, "thickness_mm": 15.0, "material": "Plywood"})

    return panels


def _write_csv(panels: list[dict]) -> str:
    output = io.StringIO()
    fieldnames = ["part", "qty", "width_cm", "height_cm", "thickness_mm", "material"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(panels)
    return output.getvalue()
