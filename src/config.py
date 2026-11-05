"""Constantes globales del proyecto."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "Datos"

COBERTURA_NOMINAL = 0.80  # cobertura nominal del rango P10–P90
FECHA_CASO = "2023-09-01"
SEED = 42
MATERIAS = ("X", "Y", "Z")
EQUIPOS = ("Equipo1", "Equipo2")
ETIQUETAS = {
    "X": "X (probable: petróleo Brent)",
    "Y": "Y (probable: acero)",
    "Z": "Z (probable: aluminio)",
}

# Criterio del horizonte confiable (usado por el pipeline y por la página de Validación de modelos)
HORIZONTE_MAX_MAPE = 0.15
HORIZONTE_MIN_COB = 0.65

# Modelo del agente del panel lateral (configurable por variable de entorno)
MODELO_AGENTE = os.environ.get("MODELO_AGENTE", "claude-opus-5-5")
