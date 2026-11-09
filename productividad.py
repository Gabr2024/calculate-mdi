"""
Calculadora de Productividad para Map Editors
---------------------------------------------
Meta mínima: 18 tareas por hora productiva
Meta ideal:  20 tareas por hora productiva

Productividad      = Tareas ÷ (Horas productivas × 18) × 100
Valor para captura = Tareas ÷ (Horas productivas × 18)

Uso:
    python productividad.py
    python productividad.py "Hice 142 tareas en 9 horas, comí 45 min"

Solo usa la biblioteca estándar de Python (3.8 o más nuevo). No hay que instalar nada.
"""

import re
import sys

META_HORA = 18   # mínimo
IDEAL_HORA = 20  # ideal
COMIDA_DEFAULT_MIN = 60

# Palabras que indican comida, tareas y horas
KW_COMIDA = r"(?:comida|com[ií]|comer|lunch|almuerzo|almorc[eé])"
KW_TAREAS = r"(?:tareas?|tasks?|edits?|ediciones?|edici[oó]n)"
KW_HORAS = r"(?:h|hr|hrs|horas?|hours?)"
NUM = r"(\d+(?:[.,]\d+)?(?::\d{1,2})?)"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def a_numero(texto):
    """Convierte '8.75', '8,75' o '8:45' a float. Devuelve None si no se puede."""
    if texto is None:
        return None
    texto = str(texto).strip()
    hm = re.fullmatch(r"(\d+):(\d{1,2})", texto)
    if hm:
        return int(hm.group(1)) + int(hm.group(2)) / 60
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def redondear(x, decimales=2):
    """Redondeo 'normal' (0.5 sube), no el redondeo bancario de round()."""
    factor = 10 ** decimales
    return int(x * factor + (0.5 if x >= 0 else -0.5)) / factor


def bonito(x):
    """142.0 -> '142', 8.25 -> '8.25', 0.8333 -> '0.83'."""
    v = redondear(x)
    return str(int(v)) if v == int(v) else f"{v:.2f}".rstrip("0").rstrip(".")


def con_signo(d):
    if d == 0:
        return "0 tareas"
    return f"{'+' if d > 0 else ''}{bonito(d)} tareas"


def minutos_a_texto(minutos):
    if minutos == 0:
        return "sin comida"
    h, m = divmod(round(minutos), 60)
    partes = []
    if h:
        partes.append(f"{h} h")
    if m:
        partes.append(f"{m} min")
    return " ".join(partes)


# ---------------------------------------------------------------------------
# Lenguaje natural
# ---------------------------------------------------------------------------
def leer_comida(s):
    """Busca el tiempo de comida en la frase. Devuelve (minutos, texto_encontrado) o None."""
    sin = re.search(rf"sin\s+{KW_COMIDA}|no\s+com[ií]", s)
    if sin:
        return 0, sin.group(0)

    tiempo = (
        r"(hora\s+y\s+media|media\s+hora|una\s+hora"
        r"|\d+\s*(?:h|hr|hrs|horas?)\s*(?:y\s*)?\d+\s*(?:min|minutos|mins|m)?"
        r"|\d+:\d{1,2}"
        r"|\d+(?:[.,]\d+)?\s*(?:min|minutos|mins|m\b|h\b|hr|hrs|horas?)?)"
    )
    m = re.search(rf"{KW_COMIDA}\s*(?:de|:|por|durante)?\s*{tiempo}", s) or re.search(
        rf"{tiempo}\s*(?:de\s*)?{KW_COMIDA}", s
    )
    if not m:
        return None

    t = m.group(1).strip()
    if re.search(r"hora\s+y\s+media", t):
        minutos = 90
    elif re.search(r"media\s+hora", t):
        minutos = 30
    elif re.search(r"una\s+hora", t):
        minutos = 60
    elif x := re.match(r"(\d+)\s*(?:h|hr|hrs|horas?)\s*(?:y\s*)?(\d+)", t):
        minutos = int(x.group(1)) * 60 + int(x.group(2))
    elif x := re.fullmatch(r"(\d+):(\d{1,2})", t):
        minutos = int(x.group(1)) * 60 + int(x.group(2))
    elif x := re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(?:min|minutos|mins|m)", t):
        minutos = a_numero(x.group(1))
    elif x := re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(?:h|hr|hrs|horas?)", t):
        minutos = a_numero(x.group(1)) * 60
    else:
        v = a_numero(t)
        if v is None:
            return None
        minutos = v if v >= 10 else v * 60  # número suelto: 10 o más = minutos
    return round(minutos), m.group(0)


def leer_frase(frase):
    """Extrae tareas, horas y comida (en minutos) de una frase libre."""
    s = frase.lower()
    resultado = {"tareas": None, "horas": None, "comida_min": None}

    comida = leer_comida(s)
    if comida:
        resultado["comida_min"] = comida[0]
        s = s.replace(comida[1], " ")  # para no confundir la comida con las horas

    if m := re.search(rf"{NUM}\s*{KW_TAREAS}", s):
        resultado["tareas"] = a_numero(m.group(1))
    if m := re.search(rf"{NUM}\s*{KW_HORAS}\b", s):
        resultado["horas"] = a_numero(m.group(1))
    elif m := re.search(r"\d+:\d{1,2}", s):
        resultado["horas"] = a_numero(m.group(0))

    # Respaldo: "142 en 9" -> primer número = tareas, segundo = horas
    if resultado["tareas"] is None or resultado["horas"] is None:
        numeros = [a_numero(n) for n in re.findall(r"\d+(?:[.,]\d+)?(?::\d{1,2})?", s)]
        resto = [n for n in numeros if n not in (resultado["tareas"], resultado["horas"])]
        if resultado["tareas"] is None and resto:
            resultado["tareas"] = resto.pop(0)
        if resultado["horas"] is None and resto:
            resultado["horas"] = resto.pop(0)
    return resultado


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------
def calcular(tareas, horas, modo="ts", comida_min=COMIDA_DEFAULT_MIN):
    """
    modo 'ts' = horas registradas en Timesheet (se resta la comida)
    modo 'pd' = horas productivas directas (no se resta nada)
    Devuelve el texto del resultado.
    """
    comida_h = comida_min / 60 if modo == "ts" else 0
    productivas = horas - comida_h
    if productivas <= 0:
        raise ValueError("Las horas productivas deben ser mayores a 0.")

    meta = productivas * META_HORA
    meta_ideal = productivas * IDEAL_HORA
    valor = tareas / meta
    pct = redondear(valor * 100)
    pct_ideal = redondear(tareas / meta_ideal * 100)
    diff = redondear(tareas - meta)
    diff_ideal = redondear(tareas - meta_ideal)

    if diff_ideal >= 0:
        estado = "[OK] Meta ideal alcanzada" if diff_ideal == 0 else \
                 f"[OK] Superaste la meta ideal por {bonito(diff_ideal)} tareas"
    elif diff >= 0:
        base = "Mínimo alcanzado" if diff == 0 else f"Mínimo superado por {bonito(diff)}"
        estado = f"[MEDIO] {base} · faltan {bonito(-diff_ideal)} para el ideal"
    else:
        estado = f"[X] Faltaron {bonito(-diff)} tareas para el mínimo"

    lineas = [f"Tareas realizadas: {bonito(tareas)}"]
    if modo == "ts":
        lineas += [
            f"Horas registradas: {bonito(horas)}",
            f"Horas de comida: {bonito(comida_h)} ({minutos_a_texto(comida_min)})",
        ]
    lineas += [
        f"Horas productivas: {bonito(productivas)}",
        "",
        f"Meta mínima (18/h): {bonito(meta)}",
        f"Meta ideal (20/h): {bonito(meta_ideal)}",
        "",
        f"Productividad: {pct:.2f}%",
        f"Valor para captura: {redondear(valor):.2f}",
        "",
        f"Diferencia contra meta mínima: {con_signo(diff)}",
        f"Diferencia contra meta ideal: {con_signo(diff_ideal)} ({pct_ideal:.2f}% del ideal)",
        "",
        estado,
    ]
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Interfaz de consola
# ---------------------------------------------------------------------------
def preguntar_numero(mensaje, default=None):
    while True:
        r = input(mensaje).strip()
        if r == "" and default is not None:
            return default
        v = a_numero(r)
        if v is not None and v >= 0:
            return v
        print("  Valor no válido, intenta de nuevo.")


def preguntar_modo():
    print("¿Qué horas vas a usar?")
    print("  1) Horas registradas (Timesheet)  -> se resta la comida")
    print("  2) Horas productivas directas     -> no se resta nada")
    while True:
        r = input("Opción [1]: ").strip()
        if r in ("", "1"):
            return "ts"
        if r == "2":
            return "pd"
        print("  Escribe 1 o 2.")


def preguntar_comida():
    r = input("Tiempo de comida (ej: 1h, 45 min, 1:15) [1 h]: ").strip().lower()
    if r == "":
        return COMIDA_DEFAULT_MIN
    encontrado = leer_comida("comida " + r)
    if encontrado:
        return encontrado[0]
    print("  No entendí, uso 1 h.")
    return COMIDA_DEFAULT_MIN


def una_vuelta(frase=None):
    modo = preguntar_modo()
    if frase is None:
        frase = input("\nEscribe tu frase (ej: 'Hice 142 tareas en 9 horas, comí 45 min')\n"
                      "o deja vacío para capturar dato por dato: ").strip()
    datos = leer_frase(frase) if frase else {"tareas": None, "horas": None, "comida_min": None}

    if datos["tareas"] is None:
        datos["tareas"] = preguntar_numero("Tareas realizadas: ")
    etiqueta = "Horas registradas" if modo == "ts" else "Horas productivas"
    if datos["horas"] is None:
        datos["horas"] = preguntar_numero(f"{etiqueta} (ej: 9 o 8:45): ")
    if modo == "ts" and datos["comida_min"] is None:
        datos["comida_min"] = preguntar_comida()

    try:
        texto = calcular(datos["tareas"], datos["horas"], modo,
                         datos["comida_min"] if datos["comida_min"] is not None else COMIDA_DEFAULT_MIN)
    except ValueError as e:
        print(f"\nERROR: {e}")
        return
    print("\n" + "=" * 50)
    print(texto)
    print("=" * 50)


def main():
    print("=== Calculadora de Productividad (mín 18/h · ideal 20/h) ===\n")
    if len(sys.argv) > 1:  # frase pasada como argumento
        una_vuelta(" ".join(sys.argv[1:]))
        return
    while True:
        una_vuelta()
        if input("\n¿Otro cálculo? (s/n) [s]: ").strip().lower() in ("n", "no"):
            break
        print()


if __name__ == "__main__":
    main()