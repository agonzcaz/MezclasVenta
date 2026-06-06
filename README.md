[README.md](https://github.com/user-attachments/files/28671105/README.md)
# Optimización de Mezcla Comercial con Modelo Markowitz

Aplicación en **Python + Streamlit** para optimizar la mezcla comercial de una distribuidora de artículos de limpieza usando la lógica del modelo de **Harry Markowitz**.

El modelo no utiliza activos bursátiles. En este caso, los activos son elementos comerciales como líneas de producto, productos, regiones, clientes o combinaciones producto-región.

## Objetivo

Encontrar una combinación óptima de mezcla comercial que balancee:

- Retorno comercial esperado
- Riesgo histórico
- Correlación entre activos comerciales
- Diversificación
- Asignación recomendada de presupuesto o meta comercial

La aplicación responde la pregunta:

> ¿Cuál es la combinación óptima de mezcla comercial para maximizar margen o ventas, con el menor riesgo histórico posible?

## Contexto de negocio

La aplicación está diseñada para una empresa distribuidora de artículos de limpieza que vende a clientes corporativos en México.

La base histórica esperada contiene ventas mensuales desde 2023 hasta el mes actual, con clientes distribuidos en seis regiones comerciales y un catálogo de SKUs agrupados en líneas de producto.

## Funcionalidades principales

- Carga de archivos `.csv`, `.xlsx` o `.xls`.
- Validación automática de columnas requeridas.
- Limpieza básica de fechas, valores numéricos y datos faltantes.
- Selección del nivel de análisis del portafolio comercial.
- Cálculo de retorno esperado por activo.
- Cálculo de riesgo histórico por activo.
- Cálculo de matriz de correlación.
- Cálculo de matriz de covarianza.
- Simulación Monte Carlo de portafolios comerciales.
- Identificación de tres carteras:
  - Mayor Sharpe comercial
  - Mayor retorno esperado
  - Menor riesgo histórico
- Gráfica de frontera eficiente comercial.
- Asignación óptima porcentual y monetaria.
- Gráfica de dona de la mezcla óptima.
- Interpretación ejecutiva automática.
- Descarga de resultados en CSV.

## Estructura del repositorio

```text
.
├── app.py
├── requirements.txt
└── README.md
```

## Requisitos

- Python 3.10 o superior recomendado.
- pip instalado.
- Navegador web para visualizar Streamlit.

## Instalación

Clona el repositorio:

```bash
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DEL_REPOSITORIO>
```

Crea un entorno virtual:

```bash
python -m venv .venv
```

Activa el entorno virtual.

En Windows:

```bash
.venv\Scripts\activate
```

En macOS o Linux:

```bash
source .venv/bin/activate
```

Instala las dependencias:

```bash
pip install -r requirements.txt
```

## Ejecución

Ejecuta la aplicación con Streamlit:

```bash
streamlit run app.py
```

Después abre la URL local que Streamlit muestre en consola, normalmente:

```text
http://localhost:8501
```

## Columnas requeridas en la base

El archivo de entrada debe contener exactamente las siguientes columnas:

| Columna | Descripción |
|---|---|
| `Fecha de venta (YYYYMM)` | Mes de venta en formato `YYYYMM`, por ejemplo `202301` |
| `Cliente` | Nombre o identificador del cliente |
| `Linea de producto` | Línea comercial del producto |
| `Producto` | SKU o nombre del producto |
| `Unidades vendidas` | Unidades vendidas en el periodo |
| `Venta en pesos (miles)` | Venta monetaria expresada en miles de pesos |
| `Costo` | Costo asociado |
| `Margen` | Margen comercial |
| `Región` | Región comercial |

## Niveles de análisis disponibles

Desde la barra lateral, el usuario puede elegir el nivel de análisis del portafolio:

1. Línea de producto
2. Producto
3. Región
4. Cliente
5. Línea de producto + Región
6. Producto + Región

Cada elemento del nivel seleccionado se trata como un activo comercial dentro del modelo Markowitz.

## Tipos de retorno comercial

La aplicación permite seleccionar tres definiciones de retorno:

| Tipo de retorno | Fórmula | Uso recomendado |
|---|---:|---|
| Margen / Venta | `Margen / Venta en pesos` | Medir rentabilidad comercial |
| Índice de venta | `Venta del activo en el mes / Venta promedio histórica del activo` | Medir tracción o crecimiento comercial |
| Participación de margen | `Margen del activo / Margen total del mes` | Medir contribución relativa al margen total |

Por defecto, el enfoque más recomendable para decisiones comerciales suele ser **Margen / Venta**, porque aproxima rentabilidad comercial.

## Lógica del modelo

La aplicación transforma la base transaccional en una matriz mensual de retornos:

```text
Mes      Activo A   Activo B   Activo C
202301   0.28       0.22       0.31
202302   0.27       0.24       0.29
202303   0.30       0.21       0.33
```

Sobre esa matriz calcula:

- Retorno esperado promedio por activo.
- Riesgo histórico como desviación estándar del retorno mensual.
- Matriz de correlación.
- Matriz de covarianza.
- Portafolios simulados mediante Monte Carlo.
- Retorno esperado del portafolio.
- Riesgo del portafolio.
- Sharpe comercial.

La fórmula conceptual del Sharpe comercial es:

```text
Sharpe comercial = (Retorno esperado del portafolio - Tasa libre de riesgo) / Riesgo del portafolio
```

La cartera óptima principal es la cartera con **mayor Sharpe comercial**.

## Salidas principales

La aplicación entrega:

- Diagnóstico comercial por activo.
- Ranking de activos por retorno esperado.
- Ranking de activos por riesgo histórico.
- Matriz y heatmap de correlación.
- Matriz y heatmap de covarianza.
- Frontera eficiente comercial.
- Cartera de mayor Sharpe.
- Cartera de mayor retorno.
- Cartera de menor riesgo.
- Asignación óptima en porcentaje.
- Asignación óptima en monto, usando el presupuesto capturado.
- Interpretación ejecutiva automática.
- Descarga de la asignación óptima en CSV.
- Descarga de la matriz mensual de retornos.

## Validaciones incluidas

La aplicación valida y controla errores frecuentes:

- Archivo sin columnas requeridas.
- Formato de fecha inválido.
- Valores no numéricos en columnas cuantitativas.
- Registros con datos críticos faltantes.
- Menos de tres meses de historia.
- Menos de dos activos disponibles.
- Activos con varianza cero.
- Portafolios con riesgo cero.
- Formatos de archivo no soportados.

Cuando existen activos con varianza cero, se excluyen de la optimización porque no aportan información útil para el cálculo de riesgo y covarianza.

## Interpretación de negocio

El modelo debe usarse como una herramienta de apoyo a la decisión, no como una recomendación automática definitiva.

Una mayor asignación a un activo comercial significa que, históricamente, ese activo mostró una mejor combinación entre retorno, riesgo y diversificación bajo la definición de retorno seleccionada.

La recomendación puede orientar decisiones como:

- Distribución de presupuesto comercial.
- Foco de fuerza de ventas.
- Priorización de inventario.
- Campañas por región o producto.
- Revisión de clientes con alto riesgo o bajo retorno.
- Balance entre productos rentables y productos defensivos.

## Limitaciones

- El modelo no predice ventas futuras por sí solo.
- La calidad del resultado depende de la calidad y granularidad de la base histórica.
- La simulación Monte Carlo no garantiza encontrar el óptimo matemático global, aunque es útil y didáctica para explorar combinaciones.
- Los retornos históricos pueden no repetirse en el futuro.
- No incorpora restricciones operativas como inventario, capacidad logística, acuerdos comerciales, descuentos o elasticidad precio-demanda.

## Dependencias

El archivo `requirements.txt` contiene:

```text
streamlit
pandas
numpy
plotly
openpyxl
```

## Próximas mejoras sugeridas

Algunas extensiones posibles para una versión productiva:

- Agregar restricciones de peso mínimo y máximo por activo.
- Permitir exclusión manual de activos comerciales.
- Incorporar presupuesto por región o línea.
- Agregar escenarios conservador, balanceado y agresivo.
- Incorporar optimización matemática con `scipy.optimize`.
- Agregar análisis de sensibilidad por presupuesto, margen y riesgo.
- Conectar con una base de datos o data warehouse.
- Incluir autenticación de usuarios.
- Publicar la app en Streamlit Community Cloud, Docker, Cloud Run o Azure App Service.

## Licencia

Uso interno o educativo. Ajustar esta sección según la política del repositorio.
