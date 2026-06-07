# 🏠 Analizador Inmobiliario

Aplicación local para analizar oportunidades inmobiliarias en portales como Idealista, Habitaclia y Fotocasa.

> **⚠️ Aviso legal**: Esta aplicación NO realiza scraping automático de ningún portal. Los datos deben ser introducidos manualmente (CSV, copia/pega de tablas o URLs). Esto respeta los términos de uso de todos los portales inmobiliarios.

---

## 🚀 Instalación y ejecución

### 1. Requisitos previos

- Python 3.11 o superior
- pip

### 2. Clonar o descargar el proyecto

```bash
# Si tienes git:
git clone <url-del-repo>
cd realestate_analyzer

# O simplemente descarga los archivos y entra en la carpeta
cd realestate_analyzer
```

### 3. Crear entorno virtual e instalar dependencias

```bash
# macOS / Linux
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Ejecutar la aplicación

```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en tu navegador en `http://localhost:8501`

---

## 📁 Estructura del proyecto

```
realestate_analyzer/
├── app.py              # Aplicación principal Streamlit
├── data_loader.py      # Carga y parseo de CSV, URLs y tablas pegadas
├── normalizer.py       # Limpieza y normalización de datos
├── scoring.py          # Sistema de puntuación (0-100)
├── analytics.py        # Análisis de mercado y gráficos
├── exporter.py         # Exportación a CSV, Excel y PDF
├── requirements.txt    # Dependencias Python
├── README.md           # Esta guía
├── data/
│   └── ejemplo_anuncios.csv   # 15 anuncios de ejemplo
└── exports/            # Carpeta de exportaciones generadas
```

---

## 📋 Formato del CSV

### Columnas aceptadas

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `titulo` | texto | Título del anuncio | Piso luminoso en Eixample |
| `precio` | número | Precio en euros | 350000 |
| `metros_cuadrados` | número | Superficie en m² | 85 |
| `habitaciones` | número | Nº de habitaciones | 3 |
| `banos` | número | Nº de baños | 2 |
| `zona` | texto | Barrio o zona | Eixample |
| `direccion` | texto | Dirección aproximada | Carrer de Balmes 120 |
| `portal` | texto | Portal de origen | Idealista |
| `url` | texto | URL del anuncio | https://... |
| `descripcion` | texto | Descripción completa | Magnífico piso... |
| `fecha_publicacion` | fecha | Fecha de publicación | 2024-01-15 |
| `planta` | número | Número de planta | 3 |
| `ascensor` | si/no | Tiene ascensor | si |
| `terraza` | si/no | Tiene terraza | no |
| `parking` | si/no | Tiene parking | si |
| `estado` | texto | Estado del inmueble | reformado |

### Valores aceptados para campos booleanos
- **Sí**: `si`, `sí`, `yes`, `true`, `1`, `s`, `y`
- **No**: `no`, `false`, `0`, `n`

### Valores aceptados para `estado`
- `reformado` / `reformada`
- `a reformar` / `para reformar`
- `obra nueva` / `nueva construcción`
- `buen estado` / `buenas condiciones`

### El separador puede ser `,` o `;` o tabuladores

---

## 🎯 Sistema de scoring (0-100 puntos)

| Criterio | Máx. puntos |
|---|---|
| Precio/m² vs media de zona | 30 |
| Precio vs presupuesto indicado | 15 |
| Metros cuadrados | 15 |
| Características (terraza, ascensor, parking, exterior) | 15 |
| Estado del inmueble | 10 |
| Potencial de inversión | 10 |
| Habitaciones | 5 |

### Penalizaciones
- Planta alta (≥4) sin ascensor: **-10 pts**
- Datos incompletos: **-5 pts**
- Precio/m² >30% sobre la media: **-8 pts**
- Descripción muy corta: **-3 pts**

### Decisiones sugeridas
| Score | Decisión |
|---|---|
| ≥70 | 🟢 Muy interesante |
| 50-69 | 🟡 Interesante |
| 30-49 | 🟠 Revisar |
| <30 | 🔴 Descartar |

---

## 📥 Cómo introducir datos

### Opción 1: Subir CSV
Descarga los resultados de búsqueda de un portal (si ofrece esta opción), adapta el formato al template y súbelo.

### Opción 2: Pegar URLs
Copia las URLs de los anuncios que te interesen (una por línea). La app los registrará y tú completas los datos manualmente.

### Opción 3: Pegar tabla
En algunos portales puedes seleccionar y copiar la tabla de resultados. Pégala directamente en la app.

### Opción 4: Datos de ejemplo
Carga los 15 anuncios de ejemplo incluidos para explorar todas las funcionalidades.

---

## 💾 Exportaciones disponibles

- **CSV**: Todos los anuncios con scores y decisiones
- **Excel**: 4 pestañas (Anuncios, Ranking, Análisis por zonas, Alertas)
- **PDF**: Resumen ejecutivo con top oportunidades y análisis de mercado

---

## 🔍 Funcionalidades principales

1. **Filtros avanzados** en el sidebar (precio, m², habitaciones, ascensor, terraza, estado, portal...)
2. **Scoring automático** de cada inmueble (0-100)
3. **Ranking de oportunidades** ordenado por score
4. **Comparación con la media de la zona**
5. **Detección de keywords** en descripción (reformado, terraza, inversión, alquilado...)
6. **Gráficos interactivos** con Plotly
7. **Análisis de mercado** por zonas con box plots, distribuciones y evolución temporal
8. **Vista detallada** de cada inmueble con gauge de score y desglose de puntuación
9. **Exportación** a CSV, Excel y PDF

---

## 🐛 Solución de problemas

### Error al instalar reportlab
```bash
pip install reportlab --upgrade
```

### Error con openpyxl
```bash
pip install openpyxl --upgrade
```

### La app no abre el navegador automáticamente
Abre manualmente: `http://localhost:8501`

### Error de encoding en CSV
Asegúrate de que tu CSV está guardado en UTF-8. En Excel: *Guardar como → CSV UTF-8*.

---

## 📝 Licencia y uso responsable

Esta herramienta es para uso personal y análisis privado de datos inmobiliarios introducidos manualmente. No automatiza ningún tipo de extracción de datos de portales inmobiliarios ni viola sus términos de uso.
