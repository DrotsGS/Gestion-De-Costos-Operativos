"""Gráficos Plotly: reciben DataFrames/Series y devuelven go.Figure (sin llamadas a Streamlit)."""
import pandas as pd
import plotly.graph_objects as go

from app.estilo import fmt_es, fmt_pct, layout, tokens


def _rgba(hex_: str, a: float) -> str:
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def fig_serie_con_atipico(cruda: pd.Series, limpia: pd.Series, fecha_atipico, nombre: str,
                          titulo: str = "", tema: str = "light") -> go.Figure:
    """Serie original (gris) y corregida (color de la materia), con el atípico marcado y etiquetado."""
    t = tokens(tema)
    f = go.Figure()
    f.add_scatter(x=cruda.index, y=cruda.values, name=f"{nombre} original", mode="lines",
                  line=dict(color=t["muted"], width=1.5))
    f.add_scatter(x=limpia.index, y=limpia.values, name=f"{nombre} corregido", mode="lines",
                  line=dict(color=t.get(nombre, t["p50"]), width=2))
    fecha = pd.Timestamp(fecha_atipico)
    orig, corr = float(cruda.loc[fecha]), float(limpia.loc[fecha])
    f.add_scatter(x=[fecha], y=[orig], name="Dato corregido", mode="markers",
                  marker=dict(color=t["critical"], size=10, line=dict(color=t["superficie"], width=2)))
    f.add_annotation(x=fecha, y=orig, text=f"Dato corregido: {fmt_es(orig)} → {fmt_es(corr)}", showarrow=True,
                     arrowhead=0, ax=60, ay=-10, font=dict(color=t["tinta"]), arrowcolor=t["muted"])
    f.update_layout(**layout(tema, titulo), hovermode="x unified")
    f.update_yaxes(title_text="Precio")
    return f


def fig_abanico(fan: pd.DataFrame, horizonte: int, titulo: str, cobertura: float | None = None, nombre: str = "Costo",
                tema: str = "light") -> go.Figure:
    """Abanico P10–P90 y P25–P75 con mediana. Tras el horizonte las bandas se atenúan (referencial).
    `cobertura` = cobertura empírica del P10–P90 (se muestra en la leyenda); sin ella, leyenda de negocio."""
    t = tokens(tema)
    x = fan.index
    n = len(fan)
    k = min(max(horizonte, 1), n)
    f = go.Figure()

    def banda(lo, hi, color, nom):
        # tramo confiable (opacidad plena) y referencial (~0.45); comparten el mes k para no dejar hueco
        for sl, op, leg in ((slice(0, k), 1.0, True), (slice(k - 1, n), 0.45, False)):
            if op < 1 and sl.stop - sl.start < 2:
                continue
            xs = x[sl]
            f.add_scatter(x=xs, y=fan[lo].iloc[sl], mode="lines", line=dict(width=0), showlegend=False,
                          hoverinfo="skip")
            f.add_scatter(x=xs, y=fan[hi].iloc[sl], mode="lines", line=dict(width=0), fill="tonexty",
                          fillcolor=_rgba(color, op), name=nom, showlegend=leg, legendgroup=nom,
                          hoverinfo="skip")

    rango = ("Rango probable (P10–P90)" if cobertura is None
             else f"P10–P90 (cobertura empírica ≈ {fmt_pct(cobertura, 0)})")
    banda("p10", "p90", t["banda_80"], rango)
    banda("p25", "p75", t["banda_50"], "P25–P75")
    f.add_scatter(x=x[:k], y=fan["p50"].iloc[:k], mode="lines", line=dict(color=t["p50"], width=2),
                  name=f"{nombre} P50", hoverinfo="skip")
    if k < n:
        f.add_scatter(x=x[k - 1:], y=fan["p50"].iloc[k - 1:], mode="lines",
                      line=dict(color=t["p50"], width=2, dash="dot"), name=f"{nombre} P50 (referencial)",
                      showlegend=False, hoverinfo="skip")
    # una sola traza (sin duplicados en el mes k) lleva el tooltip con P10, P50 y P90
    f.add_scatter(x=x, y=fan["p50"], mode="markers", marker=dict(size=8, opacity=0), showlegend=False,
                  customdata=fan[["p10", "p90"]].to_numpy(), name="Rango",
                  hovertemplate="P50 %{y:,.0f} (P10 %{customdata[0]:,.0f} – P90 %{customdata[1]:,.0f})"
                                "<extra></extra>")
    f.add_shape(type="line", x0=x[k - 1], x1=x[k - 1], y0=0, y1=1, yref="paper",
                line=dict(color=t["tinta2"], width=1))
    f.add_annotation(x=x[k - 1], y=1, yref="paper", text=f"Horizonte confiable: {horizonte} meses",
                     showarrow=False, xanchor="left", yanchor="bottom", font=dict(color=t["tinta2"]))
    f.update_layout(**layout(tema, titulo), hovermode="x unified")
    f.update_yaxes(title_text="Costo")
    return f


def fig_pesos(pesos: pd.Series, titulo: str, tema: str = "light", eje: str = "Peso en el costo") -> go.Figure:
    """Barras (pesos o parte del costo, según `eje`) de un equipo: una sola traza, color fijo por materia prima y etiqueta con el valor."""
    t = tokens(tema)
    f = go.Figure(go.Bar(
        x=list(pesos.index), y=list(pesos.values), marker=dict(color=[t.get(m, t["muted"]) for m in pesos.index],
                                                              cornerradius=4),
        text=[fmt_pct(v) for v in pesos.values], textposition="outside", textfont=dict(color=t["tinta"]),
        hovertemplate="%{x}: %{text}<extra></extra>"))
    f.update_layout(**layout(tema, titulo), bargap=0.5, showlegend=False)
    f.update_yaxes(title_text=eje, tickformat=".0%", range=[0, max(1.0, float(pesos.max()) * 1.15)])
    return f


def fig_pesos_moviles(rolling: pd.DataFrame, titulo: str, tema: str = "light") -> go.Figure:
    """Pesos en ventanas móviles, una línea por materia prima con etiqueta directa al final."""
    t = tokens(tema)
    f = go.Figure()
    for m in rolling.columns:
        f.add_scatter(x=rolling.index, y=rolling[m], mode="lines", name=m, line=dict(color=t.get(m), width=2),
                      hovertemplate="%{y:.1%}")
        f.add_annotation(x=rolling.index[-1], y=rolling[m].iloc[-1], text=m, showarrow=False, xanchor="left",
                         xshift=6, font=dict(color=t["tinta2"]))
    f.update_layout(**layout(tema, titulo), hovermode="x unified")
    f.update_yaxes(title_text="Peso", tickformat=".0%")
    return f


def fig_x_oos(x_oos: pd.DataFrame, titulo: str, tema: str = "light") -> go.Figure:
    """Rango P10–P90 simulado de X y valor real; los reales fuera del rango se marcan en estado critical."""
    t = tokens(tema)
    x = x_oos.index
    f = go.Figure()
    f.add_scatter(x=x, y=x_oos["p10"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
    f.add_scatter(x=x, y=x_oos["p90"], mode="lines", line=dict(width=0), fill="tonexty",
                  fillcolor=_rgba(t["banda_80"], 1.0), name="P10–P90 simulado", hoverinfo="skip")
    f.add_scatter(x=x, y=x_oos["p50"], mode="lines", line=dict(color=t["p50"], width=2, dash="dot"),
                  name="P50 simulado", hoverinfo="skip")
    f.add_scatter(x=x, y=x_oos["real"], mode="lines+markers", name="X real",
                  line=dict(color=t["X"], width=2), marker=dict(size=8, color=t["X"]),
                  customdata=x_oos[["p10", "p90"]].to_numpy(),
                  hovertemplate="Real %{y:,.2f} (P10 %{customdata[0]:,.2f} – P90 %{customdata[1]:,.2f})"
                                "<extra></extra>")
    fuera = x_oos[~x_oos["dentro"]]
    if len(fuera):
        f.add_scatter(x=fuera.index, y=fuera["real"], mode="markers", name="Fuera del rango",
                      marker=dict(size=10, color=t["critical"], line=dict(color=t["superficie"], width=2)))
    f.update_layout(**layout(tema, titulo), hovermode="x unified")
    f.update_yaxes(title_text="Precio de X")
    return f
