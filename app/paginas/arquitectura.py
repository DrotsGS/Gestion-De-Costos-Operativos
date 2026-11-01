"""Página 6: Arquitectura y metodología."""
import pandas as pd
import streamlit as st

from app.estilo import aplicar_css
from app.layout import con_agente
from src.config import ROOT
from src.contenido import IA_VS_AGENTE, SUPUESTOS
from src.pipeline import Resultados

INFOGRAFIA = ROOT / "docs" / "arquitectura" / "infografia_aws.svg"

# Vista simplificada del flujo (mismos componentes que la infografía)
ARQ_DOT = """
digraph G {
  rankdir=LR; bgcolor="transparent"; nodesep=0.35;
  node [shape=box, style="rounded", fontname="Helvetica", fontsize=11, color="#898781"];
  edge [color="#898781", fontname="Helvetica", fontsize=9];
  ev1 [label="EventBridge\n(mensual)"]; lam [label="Lambda\n(descarga precios)"];
  s3c [label="S3 zona cruda"]; ecs [label="ECS Fargate\n(procesamiento)"];
  glue [label="Glue + Athena\n(consultas SQL)"]; s3p [label="S3 zona procesada"];
  ev2 [label="EventBridge"]; fg [label="ECS Fargate\n(reentrenamiento)"];
  s3r [label="S3 resultados"]; ecr [label="ECR"]; app [label="App Runner\n(Streamlit)"];
  cl [label="Claude\n(Bedrock o API Anthropic)"];
  sm [label="Secrets Manager"]; cw [label="CloudWatch + Budgets"]; iam [label="IAM"];
  ev1 -> lam -> s3c -> ecs -> s3p; s3p -> glue [style=dashed];
  s3p -> fg; ev2 -> fg [label="programa"]; fg -> s3r; s3r -> app; ecr -> app; app -> cl;
  sm -> app [style=dashed]; app -> cw [style=dashed]; iam -> app [style=dashed];
}
"""

COMPONENTES = pd.DataFrame([
    ("Ingesta programada", "EventBridge + Lambda", "Dispara cada mes una función que descarga precios y compras.",
     "Sin servidores que mantener; se paga solo por ejecución."),
    ("Zona cruda", "S3 (versionado)", "Guarda los CSV originales sin tocar.",
     "Los datos originales nunca se editan; el versionado permite auditar."),
    ("Procesamiento", "ECS Fargate (job)", "Unifica formatos, audita y corrige atípicos (utils.py, auditoria.py).",
     "El trabajo dura minutos y necesita librerías científicas: un contenedor es más simple que Lambda."),
    ("Consulta ad hoc", "Glue Data Catalog + Athena", "Permite consultar con SQL las series limpias y el log de correcciones.",
     "Análisis exploratorio sin montar una base de datos."),
    ("Zona procesada", "S3", "Series mensuales limpias y registro de cada corrección.",
     "Separa dato crudo de dato curado."),
    ("Reentrenamiento", "EventBridge + ECS Fargate", "Corre el pipeline completo tras cada ingesta: fórmula, backtesting y Monte Carlo.",
     "Mantiene la fórmula y el pronóstico al día sin intervención."),
    ("Zona de resultados", "S3", "Fórmulas, pronósticos, abanicos y métricas (JSON/Parquet).",
     "La app y el agente leen resultados ya calculados: respuesta inmediata."),
    ("Aplicación web", "App Runner + ECR", "Sirve la app Streamlit desde un contenedor con HTTPS y escalado automático.",
     "Despliegue más simple que ECS + balanceador para una app interna."),
    ("Agente de IA", "Claude vía Bedrock o API de Anthropic", "Responde sobre los resultados usando herramientas.",
     "Bedrock mantiene el tráfico dentro de AWS; la API directa es más simple de arrancar."),
    ("Secretos", "Secrets Manager", "Guarda la API key y credenciales.", "Nunca van en el código ni en la imagen."),
    ("Permisos", "IAM", "Roles de mínimo privilegio por componente.", "Cada pieza accede solo a lo que necesita."),
    ("Observabilidad y costo", "CloudWatch + Budgets", "Logs, alarmas de fallos y alertas de gasto.",
     "Detecta un reentrenamiento fallido y evita sorpresas en la factura."),
], columns=["Componente", "Servicio AWS", "Qué hace", "Por qué"])

FLUJO = [
    ("Carga y limpieza", "`src/utils.py`", "unifica formatos, fechas y decimales; corrige el atípico de Z y deja registro."),
    ("Auditoría", "`src/auditoria.py`", "detecta duplicados, saltos, tramos planos y el texto oculto; produce los hallazgos."),
    ("Relación materias → equipos", "`src/relacion.py`", "estima los pesos con regresión restringida, cointegración y ventanas móviles."),
    ("Pronóstico", "`src/pronostico.py`", "backtesting de modelos contra la caminata aleatoria y simulación Monte Carlo."),
    ("Negocio", "`src/negocio.py`", "traduce los abanicos a presupuesto, reserva y veredicto de cotización."),
    ("Orquestación", "`src/pipeline.py`", "ejecuta todo y entrega un único objeto de resultados."),
    ("App y agente", "`app/` y `src/agente/`", "muestran los resultados y permiten preguntar a Claude sobre ellos."),
]

LOCAL = r"""```bash
python -m venv .venv
source .venv/bin/activate     # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/main.py
```
La app funciona sin clave: el agente muestra conversaciones de ejemplo. Para activarlo, define
`ANTHROPIC_API_KEY` en `.streamlit/secrets.toml` (`ANTHROPIC_API_KEY = "..."`) o como variable de entorno.
"""


def render(res: Resultados) -> None:
    aplicar_css()
    st.title("🏗️ Arquitectura y metodología")
    st.image(str(INFOGRAFIA), width="stretch")
    st.caption("Diseño propuesto (no desplegado)")
    with st.expander("Vista simplificada del flujo"):
        st.graphviz_chart(ARQ_DOT)

    st.subheader("Componentes y por qué se eligieron")
    st.dataframe(COMPONENTES, hide_index=True, width="stretch")

    st.subheader("Flujo de la solución")
    st.markdown("\n".join(f"{i}. **{t}** — {m}: {d}" for i, (t, m, d) in enumerate(FLUJO, 1)))

    st.subheader("IA convencional frente a agente de IA")
    st.markdown(IA_VS_AGENTE)

    st.subheader("Supuestos clave")
    st.markdown("\n".join(f"- {s}" for s in SUPUESTOS))

    st.subheader("Cómo correrlo en local")
    st.markdown(LOCAL)


con_agente("arquitectura", render)
