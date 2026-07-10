"""
backend/models/registry.py

Generic versioned model artifact registry, shared by every model component
(forecasting, and any future trained model). Not specific to LightGBM —
it just manages files + a metadata.json per version, plus a "latest" pointer.

Layout on disk:

    model_registry/
      <component>/
        v1_2026-07-10/
          <arbitrary model files>
          metadata.json
        v2_2026-07-14/
          ...
        latest.json          <- {"version_dir": "v2_2026-07-14"}

Large model binaries are expected to be .gitignored; only metadata.json
files are meant to be committed (see ML Model Specification, Section 6.10).
"""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Tuple

DEFAULT_REGISTRY_ROOT = os.environ.get("MODEL_REGISTRY_ROOT", "model_registry")


class RegistryError(Exception):
    pass


def _component_dir(component: str, registry_root: str = None) -> Path:
    if registry_root is None:
        registry_root = DEFAULT_REGISTRY_ROOT
    return Path(registry_root) / component


def save_version(
    component: str,
    version_id: str,
    model_files: Dict[str, bytes],
    metadata: dict,
    registry_root: str = None,
    set_as_latest: bool = True,
) -> Path:
    """
    Save a new model version.

    model_files: mapping of filename -> raw bytes, e.g. {"model_q50.txt": b"..."}
    metadata: dict written verbatim as metadata.json (see spec Section 6.10
              for the required fields: version, trained_on, dataset_snapshot,
              rmse_24h_vs_persistence, rmse_24h_vs_moving_average, etc.)
    """
    comp_dir = _component_dir(component, registry_root)
    version_dir = comp_dir / version_id
    version_dir.mkdir(parents=True, exist_ok=False)

    for filename, content in model_files.items():
        (version_dir / filename).write_bytes(content)

    metadata = dict(metadata)
    metadata.setdefault("version", version_id)
    (version_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    if set_as_latest:
        mark_latest(component, version_id, registry_root)

    return version_dir


def mark_latest(component: str, version_id: str, registry_root: str = None) -> None:
    comp_dir = _component_dir(component, registry_root)
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "latest.json").write_text(
        json.dumps({"version_dir": version_id}, indent=2)
    )


def load_latest(component: str, registry_root: str = None) -> Tuple[Path, dict]:
    """
    Returns (version_dir_path, metadata_dict) for the currently-active version.
    Raises RegistryError if no version has been registered yet.
    """
    comp_dir = _component_dir(component, registry_root)
    latest_pointer = comp_dir / "latest.json"
    if not latest_pointer.exists():
        raise RegistryError(
            f"No registered model found for component '{component}' under "
            f"'{comp_dir}'. Run the training script for this component first."
        )
    pointer = json.loads(latest_pointer.read_text())
    version_dir = comp_dir / pointer["version_dir"]
    metadata_path = version_dir / "metadata.json"
    if not metadata_path.exists():
        raise RegistryError(f"metadata.json missing for version at {version_dir}")
    metadata = json.loads(metadata_path.read_text())
    return version_dir, metadata


def delete_version(component: str, version_id: str, registry_root: str = None) -> None:
    """Utility for cleaning up during testing — not used in the normal training flow."""
    version_dir = _component_dir(component, registry_root) / version_id
    if version_dir.exists():
        shutil.rmtree(version_dir)
