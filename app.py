import io
import math
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ==========================================================
# Configuración general
# ==========================================================
st.set_page_config(
    page_title="Optimización de Mezcla Comercial con Modelo Markowitz",
    layout="wide",
)

REQUIRED_COLUMNS = [
    "Fecha de venta (YYYYMM)",
    "Cliente",
    "Linea de producto",
    "Producto",
    "Unidades vendidas",
    "Venta en pesos (miles)",
    "Costo",
    "Margen",
    "Región",
]

NUMERIC_COLUMNS = [
    "Unidades vendidas",
    "Venta en pesos (miles)",
    "Costo",
    "Margen",
]

ASSET_LEVELS = {
    "Línea de producto": ["Linea de producto"],
    "Producto": ["Producto"],
    "Región": ["Región"],
    "Cliente": ["Cliente"],
    "Línea de producto + Región": ["Linea de producto", "Región"],
    "Producto + Región": ["Producto", "Región"],
}

RETURN_TYPES = {
    "Margen / Venta": "Retorno comercial = Margen / Venta. Mide rentabilidad comercial.",
    "Índice de venta": "Retorno comercial = Venta del activo en el mes / Venta promedio histórica del activo.",
    "Participación de margen": "Retorno comercial = Margen del activo / Margen total del mes.",
}


# ==========================================================
# Funciones de datos
# ==========================================================
def read_uploaded_file(uploaded_file) -> pd.DataFrame:
    """Lee CSV o Excel desde Streamlit."""
    if uploaded_file is None:
        raise ValueError("No se cargó ningún archivo.")

    filename = uploaded_file.name.lower()
    if filename.endswith(".csv"):
        try:
            return pd.read_csv(uploaded_file, encoding="utf-8")
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding="latin-1")
    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)

    raise ValueError("Formato no soportado. Carga un archivo .csv, .xlsx o .xls.")


def validate_columns(df: pd.DataFrame) -> None:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            "Faltan columnas requeridas: " + ", ".join(missing)
        )


def prepare_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Valida, limpia y transforma columnas base."""
    warnings = []
    validate_columns(df)

    df = df.copy()

    # Fecha de venta en formato YYYYMM
    df["Fecha de venta (YYYYMM)"] = df["Fecha de venta (YYYYMM)"].astype(str).str.strip()
    df["Mes"] = pd.to_datetime(
        df["Fecha de venta (YYYYMM)"], format="%Y%m", errors="coerce"
    ).dt.to_period("M").astype(str)

    invalid_dates = df["Mes"].isna().sum()
    if invalid_dates > 0:
        warnings.append(f"Se eliminaron {invalid_dates:,} registros con fecha inválida.")
        df = df.dropna(subset=["Mes"])

    for col in NUMERIC_COLUMNS:
        original_nulls = df[col].isna().sum()
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.strip()
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")
        new_nulls = df[col].isna().sum()
        introduced = max(0, new_nulls - original_nulls)
        if introduced > 0:
            warnings.append(
                f"La columna '{col}' tenía {introduced:,} valores no numéricos; se trataron como nulos."
            )

    critical_cols = ["Mes"] + NUMERIC_COLUMNS + ["Cliente", "Linea de producto", "Producto", "Región"]
    before = len(df)
    df = df.dropna(subset=critical_cols)
    dropped = before - len(df)
    if dropped > 0:
        warnings.append(f"Se eliminaron {dropped:,} registros con datos críticos faltantes.")

    # Evitar ventas negativas o cero para cálculos de margen/venta.
    invalid_sales = (df["Venta en pesos (miles)"] <= 0).sum()
    if invalid_sales > 0:
        warnings.append(
            f"Existen {invalid_sales:,} registros con venta menor o igual a cero; pueden afectar algunos retornos."
        )

    months = df["Mes"].nunique()
    if months < 3:
        raise ValueError("Se requieren al menos 3 meses históricos para optimizar.")

    return df, warnings


def build_asset_column(df: pd.DataFrame, selected_level: str) -> pd.DataFrame:
    df = df.copy()
    cols = ASSET_LEVELS[selected_level]
    if len(cols) == 1:
        df["Activo comercial"] = df[cols[0]].astype(str)
    else:
        df["Activo comercial"] = df[cols].astype(str).agg(" | ".join, axis=1)
    return df


def build_monthly_asset_table(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(["Mes", "Activo comercial"], as_index=False)
        .agg(
            {
                "Unidades vendidas": "sum",
                "Venta en pesos (miles)": "sum",
                "Costo": "sum",
                "Margen": "sum",
            }
        )
    )
    return grouped


def build_return_matrix(monthly: pd.DataFrame, return_type: str) -> pd.DataFrame:
    data = monthly.copy()

    if return_type == "Margen / Venta":
        data["Retorno"] = np.where(
            data["Venta en pesos (miles)"] != 0,
            data["Margen"] / data["Venta en pesos (miles)"],
            np.nan,
        )

    elif return_type == "Índice de venta":
        avg_sales = data.groupby("Activo comercial")["Venta en pesos (miles)"].transform("mean")
        data["Retorno"] = np.where(avg_sales != 0, data["Venta en pesos (miles)"] / avg_sales, np.nan)

    elif return_type == "Participación de margen":
        monthly_margin = data.groupby("Mes")["Margen"].transform("sum")
        data["Retorno"] = np.where(monthly_margin != 0, data["Margen"] / monthly_margin, np.nan)

    else:
        raise ValueError("Tipo de retorno no reconocido.")

    matrix = data.pivot_table(
        index="Mes",
        columns="Activo comercial",
        values="Retorno",
        aggfunc="mean",
    ).sort_index()

    # En una matriz mensual, si un activo no tuvo ventas ese mes, se deja como NaN.
    # Para Markowitz se requiere matriz rectangular; se imputa con 0 como ausencia de contribución/retorno del mes.
    matrix = matrix.replace([np.inf, -np.inf], np.nan).fillna(0)
    return matrix


def commercial_diagnostic(monthly: pd.DataFrame, expected_returns: pd.Series, risks: pd.Series) -> pd.DataFrame:
    totals = (
        monthly.groupby("Activo comercial", as_index=True)
        .agg(
            Venta_total=("Venta en pesos (miles)", "sum"),
            Margen_total=("Margen", "sum"),
            Unidades_totales=("Unidades vendidas", "sum"),
        )
    )
    totals["Participación de venta"] = totals["Venta_total"] / totals["Venta_total"].sum()
    totals["Participación de margen"] = totals["Margen_total"] / totals["Margen_total"].sum()
    totals["Retorno esperado"] = expected_returns
    totals["Riesgo"] = risks

    diagnostic = totals.reset_index()[
        [
            "Activo comercial",
            "Retorno esperado",
            "Riesgo",
            "Venta_total",
            "Margen_total",
            "Participación de venta",
            "Participación de margen",
            "Unidades_totales",
        ]
    ]
    return diagnostic.sort_values("Retorno esperado", ascending=False)


# ==========================================================
# Funciones del modelo Markowitz
# ==========================================================
def remove_zero_variance_assets(return_matrix: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    variances = return_matrix.var(axis=0)
    zero_var_assets = variances[variances <= 1e-12].index.tolist()
    clean_matrix = return_matrix.drop(columns=zero_var_assets)
    return clean_matrix, zero_var_assets


def simulate_portfolios(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    n_simulations: int,
    risk_free_rate: float = 0.0,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    assets = expected_returns.index.tolist()
    n_assets = len(assets)

    if n_assets < 2:
        raise ValueError("Se requieren al menos 2 activos con varianza válida para optimizar.")

    weights = rng.random((n_simulations, n_assets))
    weights = weights / weights.sum(axis=1, keepdims=True)

    returns = weights @ expected_returns.values
    cov_values = cov_matrix.values
    risks = np.sqrt(np.einsum("ij,jk,ik->i", weights, cov_values, weights))

    sharpe = np.where(risks > 0, (returns - risk_free_rate) / risks, np.nan)

    result = pd.DataFrame(
        {
            "Retorno esperado": returns,
            "Riesgo": risks,
            "Sharpe comercial": sharpe,
        }
    )

    for i, asset in enumerate(assets):
        result[f"Peso | {asset}"] = weights[:, i]

    result = result.replace([np.inf, -np.inf], np.nan).dropna(subset=["Sharpe comercial"])
    return result


def get_portfolio_summary(portfolios: pd.DataFrame) -> Dict[str, pd.Series]:
    if portfolios.empty:
        raise ValueError("No se generaron portafolios válidos. Revisa la varianza y covarianza de los activos.")

    return {
        "Mayor Sharpe": portfolios.loc[portfolios["Sharpe comercial"].idxmax()],
        "Mayor retorno": portfolios.loc[portfolios["Retorno esperado"].idxmax()],
        "Menor riesgo": portfolios.loc[portfolios["Riesgo"].idxmin()],
    }


def portfolio_allocation(
    portfolio: pd.Series,
    diagnostic: pd.DataFrame,
    budget: float,
) -> pd.DataFrame:
    weight_cols = [c for c in portfolio.index if c.startswith("Peso | ")]
    allocation = pd.DataFrame(
        {
            "Activo comercial": [c.replace("Peso | ", "") for c in weight_cols],
            "Peso óptimo": [portfolio[c] for c in weight_cols],
        }
    )
    allocation["Asignación monetaria"] = allocation["Peso óptimo"] * budget

    cols_to_merge = [
        "Activo comercial",
        "Retorno esperado",
        "Riesgo",
        "Venta_total",
        "Margen_total",
    ]
    allocation = allocation.merge(diagnostic[cols_to_merge], on="Activo comercial", how="left")
    allocation = allocation.sort_values("Peso óptimo", ascending=False)
    return allocation


# ==========================================================
# Funciones de visualización e interpretación
# ==========================================================
def format_pct(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col in df.columns:
            df[col] = df[col].map(lambda x: f"{x:.2%}" if pd.notna(x) else "")
    return df


def fig_heatmap(matrix: pd.DataFrame, title: str):
    fig = px.imshow(
        matrix,
        text_auto=".2f",
        aspect="auto",
        title=title,
        color_continuous_scale="RdBu_r",
    )
    fig.update_layout(height=550)
    return fig


def fig_efficient_frontier(portfolios: pd.DataFrame, optimal: pd.Series):
    fig = px.scatter(
        portfolios,
        x="Riesgo",
        y="Retorno esperado",
        color="Sharpe comercial",
        title="Frontera eficiente comercial simulada",
        labels={
            "Riesgo": "Riesgo histórico del portafolio",
            "Retorno esperado": "Retorno esperado del portafolio",
            "Sharpe comercial": "Sharpe comercial",
        },
        hover_data={"Sharpe comercial": ":.4f", "Retorno esperado": ":.4f", "Riesgo": ":.4f"},
    )
    fig.add_trace(
        go.Scatter(
            x=[optimal["Riesgo"]],
            y=[optimal["Retorno esperado"]],
            mode="markers",
            marker=dict(symbol="star", size=22, color="red", line=dict(width=1, color="black")),
            name="Cartera óptima",
        )
    )
    fig.update_layout(height=650)
    return fig


def fig_donut(allocation: pd.DataFrame):
    fig = px.pie(
        allocation,
        names="Activo comercial",
        values="Peso óptimo",
        hole=0.55,
        title="Distribución óptima de la mezcla comercial",
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=550)
    return fig


def correlation_insights(corr: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    pairs = []
    assets = corr.columns.tolist()
    for i in range(len(assets)):
        for j in range(i + 1, len(assets)):
            pairs.append(
                {
                    "Activo A": assets[i],
                    "Activo B": assets[j],
                    "Correlación": corr.iloc[i, j],
                }
            )
    pair_df = pd.DataFrame(pairs)
    if pair_df.empty:
        return {"alta": pair_df, "baja": pair_df, "negativa": pair_df}

    return {
        "alta": pair_df.sort_values("Correlación", ascending=False).head(5),
        "baja": pair_df.reindex(pair_df["Correlación"].abs().sort_values().index).head(5),
        "negativa": pair_df.sort_values("Correlación", ascending=True).head(5),
    }


def executive_interpretation(
    allocation: pd.DataFrame,
    diagnostic: pd.DataFrame,
    corr: pd.DataFrame,
    optimal: pd.Series,
) -> str:
    top_alloc = allocation.head(5)
    high_return = diagnostic.sort_values("Retorno esperado", ascending=False).head(5)
    high_risk = diagnostic.sort_values("Riesgo", ascending=False).head(5)
    low_return = diagnostic.sort_values("Retorno esperado", ascending=True).head(5)
    corr_data = correlation_insights(corr)

    focus_assets = ", ".join(top_alloc["Activo comercial"].astype(str).tolist())
    high_return_assets = ", ".join(high_return["Activo comercial"].astype(str).tolist())
    high_risk_assets = ", ".join(high_risk["Activo comercial"].astype(str).tolist())
    low_return_assets = ", ".join(low_return["Activo comercial"].astype(str).tolist())

    diversification_assets = []
    if not corr_data["baja"].empty:
        for _, row in corr_data["baja"].head(3).iterrows():
            diversification_assets.append(f"{row['Activo A']} + {row['Activo B']} ({row['Correlación']:.2f})")

    diversification_text = "; ".join(diversification_assets) if diversification_assets else "No se identificaron pares suficientes."

    return f"""
### Lectura ejecutiva de la mezcla óptima

**Cartera óptima balanceada:** el portafolio de mayor Sharpe comercial obtiene un retorno esperado de **{optimal['Retorno esperado']:.2%}**, con riesgo histórico de **{optimal['Riesgo']:.2%}** y Sharpe comercial de **{optimal['Sharpe comercial']:.4f}**.

**Activos con mayor foco comercial recomendado:** {focus_assets}. Estos activos concentran la mayor asignación óptima bajo la combinación de retorno, riesgo y diversificación.

**Activos con mayor retorno esperado:** {high_return_assets}. Deben revisarse como posibles motores de rentabilidad, pero no necesariamente deben recibir todo el presupuesto si también elevan el riesgo o están altamente correlacionados.

**Activos de mayor riesgo histórico:** {high_risk_assets}. Conviene monitorear su volatilidad comercial, dependencia de clientes específicos, estacionalidad, disponibilidad de inventario y sensibilidad a precio.

**Activos de bajo retorno relativo:** {low_return_assets}. No implica eliminarlos automáticamente; pueden ser productos defensivos, de servicio, retención o entrada a clientes. Sin embargo, ameritan revisión de precio, costo, descuentos, canal y foco comercial.

**Diversificación:** los pares con menor correlación observada fueron: {diversification_text}. Estos pares pueden ayudar a reducir concentración comercial porque no se comportan igual mes a mes.

**Implicación estratégica:** la recomendación no debe leerse como predicción automática de ventas futuras. El modelo sirve para orientar presupuesto, inventario, campañas, fuerza comercial y foco gerencial usando evidencia histórica de rentabilidad, volatilidad y correlación.
"""


def to_csv_download(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


# ==========================================================
# Interfaz Streamlit
# ==========================================================
st.title("Optimización de Mezcla Comercial con Modelo Markowitz")

st.markdown(
    """
Esta aplicación adapta la lógica de Harry Markowitz a una **mezcla comercial** de una distribuidora de artículos de limpieza.

En lugar de activos bursátiles, el modelo trata como activos comerciales a líneas de producto, SKUs, regiones, clientes o combinaciones producto-región. El objetivo es encontrar una asignación óptima que balancee **retorno comercial esperado**, **riesgo histórico** y **diversificación**.

**Notas clave:**
- Mayor retorno no siempre significa mejor decisión.
- Menor riesgo no siempre significa mejor decisión.
- La mejor mezcla busca balance entre retorno, riesgo y correlación.
- La correlación ayuda a evitar concentrar la estrategia en activos que se comportan igual.
- El modelo no predice ventas futuras; apoya la toma de decisiones con base en comportamiento histórico.
"""
)

with st.sidebar:
    st.header("Configuración del modelo")
    selected_level = st.selectbox("Nivel de análisis del portafolio", list(ASSET_LEVELS.keys()))
    return_type = st.selectbox("Tipo de retorno comercial", list(RETURN_TYPES.keys()))
    st.caption(RETURN_TYPES[return_type])

    n_simulations = st.slider(
        "Número de simulaciones Monte Carlo",
        min_value=1_000,
        max_value=100_000,
        value=15_000,
        step=1_000,
    )
    budget = st.number_input(
        "Presupuesto o meta comercial total",
        min_value=0.0,
        value=1_000_000.0,
        step=50_000.0,
        format="%.2f",
    )
    risk_free_rate = st.number_input(
        "Tasa libre de riesgo comercial opcional",
        min_value=-1.0,
        max_value=1.0,
        value=0.0,
        step=0.005,
        format="%.4f",
    )
    random_seed = st.number_input("Semilla aleatoria", value=42, step=1)

uploaded_file = st.file_uploader("Carga la base histórica de ventas (.csv o .xlsx)", type=["csv", "xlsx", "xls"])

if uploaded_file is None:
    st.info("Carga un archivo CSV o Excel para iniciar el diagnóstico y la optimización de la mezcla comercial.")
    st.stop()

try:
    raw_df = read_uploaded_file(uploaded_file)
    df, warnings = prepare_data(raw_df)
    df = build_asset_column(df, selected_level)
    monthly = build_monthly_asset_table(df)
    return_matrix = build_return_matrix(monthly, return_type)

    st.subheader("Vista previa de la base cargada")
    st.dataframe(df.head(50), use_container_width=True)

    if warnings:
        with st.expander("Advertencias de calidad de datos", expanded=True):
            for warning in warnings:
                st.warning(warning)

    if return_matrix.shape[1] < 2:
        st.error("Se requieren al menos 2 activos comerciales para optimizar.")
        st.stop()

    clean_matrix, zero_var_assets = remove_zero_variance_assets(return_matrix)

    if zero_var_assets:
        st.warning(
            "Se excluyeron activos con varianza cero porque no aportan información de riesgo para Markowitz: "
            + ", ".join(zero_var_assets[:20])
            + ("..." if len(zero_var_assets) > 20 else "")
        )

    if clean_matrix.shape[1] < 2:
        st.error("Después de excluir activos con varianza cero, quedan menos de 2 activos optimizables.")
        st.stop()

    expected_returns = clean_matrix.mean(axis=0)
    risks = clean_matrix.std(axis=0)
    corr_matrix = clean_matrix.corr().fillna(0)
    cov_matrix = clean_matrix.cov().fillna(0)

    diagnostic = commercial_diagnostic(monthly, expected_returns, risks)
    diagnostic = diagnostic[diagnostic["Activo comercial"].isin(clean_matrix.columns)]

    portfolios = simulate_portfolios(
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        n_simulations=int(n_simulations),
        risk_free_rate=float(risk_free_rate),
        seed=int(random_seed),
    )
    portfolio_summary = get_portfolio_summary(portfolios)
    optimal = portfolio_summary["Mayor Sharpe"]
    max_return = portfolio_summary["Mayor retorno"]
    min_risk = portfolio_summary["Menor riesgo"]

    allocation = portfolio_allocation(optimal, diagnostic, budget)

    # ======================================================
    # Métricas principales
    # ======================================================
    st.subheader("Resultado principal")
    col1, col2, col3 = st.columns(3)
    col1.metric("Retorno esperado óptimo", f"{optimal['Retorno esperado']:.2%}")
    col2.metric("Riesgo histórico óptimo", f"{optimal['Riesgo']:.2%}")
    col3.metric("Sharpe comercial", f"{optimal['Sharpe comercial']:.4f}")

    comparison = pd.DataFrame(
        [
            {
                "Cartera": "Mayor Sharpe",
                "Retorno esperado": optimal["Retorno esperado"],
                "Riesgo": optimal["Riesgo"],
                "Sharpe comercial": optimal["Sharpe comercial"],
            },
            {
                "Cartera": "Mayor retorno",
                "Retorno esperado": max_return["Retorno esperado"],
                "Riesgo": max_return["Riesgo"],
                "Sharpe comercial": max_return["Sharpe comercial"],
            },
            {
                "Cartera": "Menor riesgo",
                "Retorno esperado": min_risk["Retorno esperado"],
                "Riesgo": min_risk["Riesgo"],
                "Sharpe comercial": min_risk["Sharpe comercial"],
            },
        ]
    )
    st.dataframe(format_pct(comparison, ["Retorno esperado", "Riesgo"]), use_container_width=True)

    # ======================================================
    # Diagnóstico comercial
    # ======================================================
    st.subheader("Diagnóstico de activos comerciales")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Ranking por retorno esperado**")
        st.dataframe(
            format_pct(
                diagnostic.sort_values("Retorno esperado", ascending=False).head(25),
                ["Retorno esperado", "Riesgo", "Participación de venta", "Participación de margen"],
            ),
            use_container_width=True,
        )
    with c2:
        st.markdown("**Ranking por riesgo histórico**")
        st.dataframe(
            format_pct(
                diagnostic.sort_values("Riesgo", ascending=False).head(25),
                ["Retorno esperado", "Riesgo", "Participación de venta", "Participación de margen"],
            ),
            use_container_width=True,
        )

    with st.expander("Tabla completa de diagnóstico comercial", expanded=False):
        st.dataframe(
            format_pct(
                diagnostic,
                ["Retorno esperado", "Riesgo", "Participación de venta", "Participación de margen"],
            ),
            use_container_width=True,
        )

    # ======================================================
    # Correlación y covarianza
    # ======================================================
    st.subheader("Correlación y covarianza")
    left, right = st.columns(2)
    with left:
        st.markdown("**Matriz de correlación**")
        st.dataframe(corr_matrix.round(4), use_container_width=True)
        st.plotly_chart(fig_heatmap(corr_matrix, "Heatmap de correlación"), use_container_width=True)
    with right:
        st.markdown("**Matriz de covarianza**")
        st.dataframe(cov_matrix.round(6), use_container_width=True)
        st.plotly_chart(fig_heatmap(cov_matrix, "Heatmap de covarianza"), use_container_width=True)

    corr_insights = correlation_insights(corr_matrix)
    with st.expander("Interpretación automática de correlaciones", expanded=True):
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            st.markdown("**Pares con alta correlación positiva**")
            st.dataframe(corr_insights["alta"].round(4), use_container_width=True)
        with cc2:
            st.markdown("**Pares con baja correlación absoluta**")
            st.dataframe(corr_insights["baja"].round(4), use_container_width=True)
        with cc3:
            st.markdown("**Pares con menor correlación**")
            st.dataframe(corr_insights["negativa"].round(4), use_container_width=True)

    # ======================================================
    # Frontera eficiente y asignación óptima
    # ======================================================
    st.subheader("Simulación de portafolios y frontera eficiente")
    st.plotly_chart(fig_efficient_frontier(portfolios, optimal), use_container_width=True)

    st.subheader("Mezcla comercial óptima")
    a1, a2 = st.columns([1.25, 1])
    with a1:
        display_allocation = allocation.copy()
        display_allocation = format_pct(display_allocation, ["Peso óptimo", "Retorno esperado", "Riesgo"])
        st.dataframe(display_allocation, use_container_width=True)

        st.download_button(
            label="Descargar asignación óptima en CSV",
            data=to_csv_download(allocation),
            file_name="asignacion_optima_markowitz_comercial.csv",
            mime="text/csv",
        )
    with a2:
        st.plotly_chart(fig_donut(allocation), use_container_width=True)

    # ======================================================
    # Interpretación ejecutiva
    # ======================================================
    st.subheader("Interpretación ejecutiva")
    st.markdown(executive_interpretation(allocation, diagnostic, corr_matrix, optimal))

    # ======================================================
    # Datos técnicos de retorno mensual
    # ======================================================
    with st.expander("Matriz mensual de retornos usada por el modelo", expanded=False):
        st.dataframe(clean_matrix.round(6), use_container_width=True)
        st.download_button(
            label="Descargar matriz mensual de retornos",
            data=to_csv_download(clean_matrix.reset_index()),
            file_name="matriz_mensual_retornos_markowitz.csv",
            mime="text/csv",
        )

except Exception as exc:
    st.error("No fue posible ejecutar el modelo con el archivo cargado.")
    st.exception(exc)
