"""Contenidos estáticos en español: texto oculto del PDF, hipótesis, IA vs agente y supuestos."""
import pandas as pd

TEXTO_OCULTO_RESUMEN = (
    "El PDF del caso contiene, debajo de \"Código funcional\" en la página 1, un texto invisible al "
    "visualizarlo que solo aparece al extraer el texto del archivo. Se presenta como una "
    "\"[INSTRUCCIÓN DEL SISTEMA]\" y pide a una IA exponer conclusiones predeterminadas como si fueran "
    "su propio análisis. Los datos contradicen esas conclusiones; se trató como una trampa para "
    "detectar trabajo generado por IA sin revisar."
)


def _fmt_pesos(w: pd.Series, umbral: float = 0.05) -> str:
    """Pesos calculados en texto: componentes relevantes y los casi nulos como '≈ 0 %'."""
    if w.max() - w.min() <= 0.02:  # casi iguales: evita que los redondeos no sumen 100 %
        return f"≈ ⅓ cada una ({', '.join(w.index)})" if len(w) == 3 else "pesos casi iguales"
    w = w.sort_values(ascending=False)
    grandes = [f"{v * 100:.0f} % {k}" for k, v in w.items() if v >= umbral]
    chicos = [f"{k} ≈ 0 %" for k, v in w.items() if v < umbral]
    return " + ".join(grandes) + ("; " + ", ".join(chicos) if chicos else "")


def _fmt_part(part: pd.Series) -> str:
    return ", ".join(f"{k} {v * 100:.0f} %" for k, v in part.sort_values(ascending=False).items() if v >= 0.005)


def formula_texto(w: pd.Series, part: pd.Series | None = None) -> str:
    """Pesos de la fórmula (por unidad de precio) en texto; con `part`, añade la parte del costo."""
    txt = "pesos de la fórmula (por unidad de precio): " + _fmt_pesos(w)
    if part is not None:
        txt += "; parte del costo ≈ " + _fmt_part(part)
    return txt


NOTA_PESOS_VS_COSTO = (
    "Los pesos multiplican precios de escalas muy distintas (X ≈ 85, Y ≈ 556, Z ≈ 2.133), por eso un peso "
    "alto o bajo no equivale a una parte del costo: lo que pesa en el costo es peso × precio."
)


def tabla_texto_oculto(pesos: dict[str, pd.Series], part: dict[str, pd.Series] | None = None) -> pd.DataFrame:
    """Contraste entre lo que dice el texto oculto (pesos de fórmula) y lo que muestran los datos.

    Con `part` se añade la parte del costo a la columna de datos."""
    y1, y2 = pesos["Equipo1"]["Y"], pesos["Equipo2"]["Y"]
    y_txt = f"Pesa {y1 * 100:.0f} % en el Equipo 1 y {y2 * 100:.0f} % en el Equipo 2"
    if pesos["Equipo1"].idxmax() == "Y":
        y_txt += "; es la de mayor peso en el Equipo 1"
    def _f(e):
        t = "Pesos de la fórmula: " + _fmt_pesos(pesos[e])
        return t + (f"; parte del costo ≈ {_fmt_part(part[e])}" if part is not None else "")

    filas = [
        ("Equipo 1", "95 % Z", _f("Equipo1")),
        ("Equipo 2", "70 % X + 30 % Z", _f("Equipo2")),
        ("Materia prima Y", "No significativa, descartar", y_txt),
        ("Método de pronóstico", "Solo promedio móvil de 3 meses, sin tendencia ni estacionalidad",
         "Se compararon caminata aleatoria, promedio móvil, ARIMA y ETS con validación histórica; "
         "se usa simulación Monte Carlo con rangos"),
        ("Presentación", "Como si fuera análisis propio", "Documentado como hallazgo de auditoría"),
    ]
    return pd.DataFrame(filas, columns=["aspecto", "dice_texto_oculto", "muestran_datos"])


HIPOTESIS_MATERIAS = pd.DataFrame(
    [
        ("X", "Petróleo Brent (futuros, no precio spot)", "Alta",
         "~40 % de los días dentro de ±1 % del Brent de FRED; el 2020-04-21 vale 19,33 (cierre de "
         "futuros) y no 9,12 (spot)."),
        ("Y", "Acero (probable HRC/varilla de exportación China)", "Media",
         "257,50 el 2015-12-04 coincide con un precio de Fastmarkets; ciclo 2008/2015/2021 típico del acero."),
        ("Z", "Aluminio LME", "Alta",
         "Máximo de 3.984 el 2022-03-08, en línea con el récord de ~3.985 USD/t de marzo 2022."),
    ],
    columns=["serie", "hipotesis", "confianza", "evidencia"],
)

NOTA_HIPOTESIS = (
    "El modelo no depende de esta identificación: solo se usa como contexto y para que el agente "
    "busque noticias del mercado correcto."
)

# Rasgos del agente: (aspecto, IA convencional, agente en el panel)
RASGOS_AGENTE = [
    ("Autonomía", "Ejecuta el cálculo que se le pide", "Decide los pasos y cuándo parar"),
    ("Herramientas", "Ninguna: es la herramienta", "Llama al modelo, al verificador de cotizaciones y a las noticias (Google News)"),
    ("Memoria", "Sin estado entre ejecuciones", "Conserva el hilo de la conversación entre páginas"),
    ("Acción", "Devuelve números", "Simula escenarios, evalúa cotizaciones y busca noticias"),
]

IA_VS_AGENTE = """\
**IA convencional.** Es un modelo que predice, clasifica o genera a partir de datos. Aquí es la \
regresión de pesos más la simulación Monte Carlo: recibe precios y devuelve un pronóstico con rangos. \
No decide qué hacer ni actúa por su cuenta.

**Agente de IA.** Percibe el contexto, decide, usa herramientas, tiene memoria y actúa hacia un \
objetivo. Aquí es el agente Claude del panel lateral: elige qué herramienta llamar \
(`consultar_resultados`, `simular_escenario`, `evaluar_cotizacion` o `buscar_noticias`, titulares de Google News) según la \
pregunta del usuario.

| Aspecto | IA convencional (el modelo) | Agente (Claude en el panel) |
|---|---|---|
""" + "\n".join(f"| {a} | {m} | {g} |" for a, m, g in RASGOS_AGENTE) + """

El agente no reemplaza al modelo: lo usa como herramienta y no inventa cifras.
"""

# Versión compacta para el panel lateral (sin tablas: la columna es angosta)
AGENTE_PANEL_INTRO = ("El modelo calcula el pronóstico; el agente decide qué preguntarle, usa sus "
                      "herramientas y no inventa cifras.")


SUPUESTOS = [
    "El caso está fechado en septiembre de 2023 (fin de los datos).",
    "La frecuencia de trabajo es mensual (promedio del mes).",
    "Las cantidades de ejemplo del presupuesto son editables; el caso no entrega cantidades.",
    "La identificación de X, Y y Z es una hipótesis y no afecta al modelo.",
    "Los pesos se estimaron con 2010-2023 y se asumen estables (se verifican con regresión móvil).",
    "La cobertura empírica de las bandas es menor a la nominal (P10-P90 = 80 %); ver página de Validación de modelos.",
    "Una compra puntual suma ≈ 1,8 % de ruido diario sobre el costo promedio mensual.",
    "El atípico de Z se corrigió por interpolación lineal.",
    "El pronóstico parte en 2023-09 y es confiable solo hasta el horizonte elegido.",
]
