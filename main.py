import json
import os
import threading
import stripe
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# =====================================================================
# CONFIGURACIÓN
# =====================================================================
TOKEN = os.environ["TELEGRAM_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

LINK_INICIO  = "https://buy.stripe.com/14AbJ13XUfU8fwv8R99fW00"  # 5€
LINK_SINTOMA = "https://buy.stripe.com/aFabJ1cuqdM04RRgjB9fW01"  # 10€
LINK_CODIGO  = "https://buy.stripe.com/bJe8wPami9vKfwv3wP9fW02"  # 30€

STATS_FILE = "stats.json"

# =====================================================================
# KEEP-ALIVE — servidor HTTP para que Replit no duerma el proceso
# =====================================================================
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot IVECO activo")
    def log_message(self, format, *args):
        pass  # Silenciar logs del servidor

def iniciar_servidor():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), KeepAlive)
    server.serve_forever()

threading.Thread(target=iniciar_servidor, daemon=True).start()

# =====================================================================
# BASE DE DATOS CÓDIGOS REALES IVECO
# =====================================================================
CODIGOS = {
    # ===== MOTOR =====
    "111 FMI 1":  {"desc": "Presión aceite motor baja",                "sistema": "Motor",    "diag": ["Verificar nivel aceite", "Sensor presión aceite", "Bomba aceite", "Filtro aceite obstruido"]},
    "111 FMI 18": {"desc": "Presión aceite motor muy baja",            "sistema": "Motor",    "diag": ["Parar motor inmediatamente", "Nivel aceite", "Bomba aceite averiada", "Fuga interna"]},
    "100 FMI 1":  {"desc": "Presión aceite baja advertencia",          "sistema": "Motor",    "diag": ["Nivel aceite", "Sensor presión", "Circuito lubricación", "Filtro aceite"]},
    "100 FMI 18": {"desc": "Presión aceite crítica",                   "sistema": "Motor",    "diag": ["Parar motor", "Bomba aceite", "Fuga aceite", "Cojinetes"]},
    "110 FMI 0":  {"desc": "Temperatura refrigerante alta",            "sistema": "Motor",    "diag": ["Nivel refrigerante", "Termostato", "Bomba agua", "Radiador obstruido"]},
    "110 FMI 15": {"desc": "Temperatura refrigerante muy alta",        "sistema": "Motor",    "diag": ["Parar motor", "Nivel refrigerante", "Fuga circuito", "Ventilador"]},
    "175 FMI 0":  {"desc": "Temperatura aceite motor alta",            "sistema": "Motor",    "diag": ["Nivel aceite", "Enfriador aceite", "Bomba agua", "Sensor temperatura aceite"]},
    "105 FMI 0":  {"desc": "Temperatura aire admisión alta",           "sistema": "Motor",    "diag": ["Intercooler", "Manguitos intercooler", "Sensor temperatura admisión", "Turbo"]},
    "105 FMI 3":  {"desc": "Sensor temperatura admisión cortocircuito","sistema": "Motor",    "diag": ["Sensor MAT", "Cableado sensor", "Conector oxidado", "ECM"]},
    "102 FMI 1":  {"desc": "Presión boost turbo baja",                 "sistema": "Motor",    "diag": ["Filtro aire obstruido", "Manguitos rotos", "Turbo averiado", "Sensor MAP"]},
    "102 FMI 2":  {"desc": "Sensor presión boost señal errática",      "sistema": "Motor",    "diag": ["Sensor MAP", "Cableado sensor", "Turbo", "Admisión"]},
    "102 FMI 3":  {"desc": "Sensor presión boost cortocircuito",       "sistema": "Motor",    "diag": ["Sensor MAP", "Cableado", "Conector", "ECM"]},
    "102 FMI 4":  {"desc": "Sensor presión boost circuito abierto",    "sistema": "Motor",    "diag": ["Sensor MAP", "Cableado roto", "Conector", "ECM"]},
    "190 FMI 0":  {"desc": "Régimen motor excesivo",                   "sistema": "Motor",    "diag": ["Sensor régimen CKP", "Centralita motor ECM", "Cableado sensor", "Actuador acelerador"]},
    "190 FMI 2":  {"desc": "Sensor régimen motor señal errática",      "sistema": "Motor",    "diag": ["Sensor CKP sucio o dañado", "Corona reluctancia", "Entrehierro sensor", "Cableado"]},
    "190 FMI 8":  {"desc": "Sensor régimen motor señal anormal",       "sistema": "Motor",    "diag": ["Sensor CKP", "Corona reluctancia dañada", "Interferencias", "ECM"]},
    "723 FMI 2":  {"desc": "Sensor árbol levas señal errática",        "sistema": "Motor",    "diag": ["Sensor CMP", "Rueda fónica", "Entrehierro", "Sincronismo distribución"]},
    "723 FMI 8":  {"desc": "Sensor árbol levas sin señal",             "sistema": "Motor",    "diag": ["Sensor CMP", "Cableado", "Rueda fónica", "Distribución"]},
    "157 FMI 1":  {"desc": "Presión rail combustible baja",            "sistema": "Motor",    "diag": ["Filtro combustible", "Bomba alta presión", "Regulador presión rail", "Fugas circuito"]},
    "157 FMI 18": {"desc": "Presión rail combustible muy baja",        "sistema": "Motor",    "diag": ["Bomba alta presión averiada", "Fuga en rail", "Válvula reguladora", "Inyectores"]},
    "157 FMI 0":  {"desc": "Presión rail combustible alta",            "sistema": "Motor",    "diag": ["Válvula limitadora presión", "Regulador presión", "Sensor presión rail", "Inyectores"]},
    "94 FMI 1":   {"desc": "Presión combustible baja alimentación",    "sistema": "Motor",    "diag": ["Filtro combustible obstruido", "Bomba baja presión", "Aire en circuito", "Depósito vacío"]},
    "94 FMI 18":  {"desc": "Presión combustible muy baja",             "sistema": "Motor",    "diag": ["Bomba alimentación averiada", "Filtro combustible colmatado", "Fugas", "Válvula retención"]},
    "651 FMI 5":  {"desc": "Inyector cilindro 1 circuito abierto",     "sistema": "Motor",    "diag": ["Inyector cilindro 1", "Cableado inyector", "Conector", "ECM"]},
    "652 FMI 5":  {"desc": "Inyector cilindro 2 circuito abierto",     "sistema": "Motor",    "diag": ["Inyector cilindro 2", "Cableado inyector", "Conector", "ECM"]},
    "653 FMI 5":  {"desc": "Inyector cilindro 3 circuito abierto",     "sistema": "Motor",    "diag": ["Inyector cilindro 3", "Cableado inyector", "Conector", "ECM"]},
    "654 FMI 5":  {"desc": "Inyector cilindro 4 circuito abierto",     "sistema": "Motor",    "diag": ["Inyector cilindro 4", "Cableado inyector", "Conector", "ECM"]},
    "655 FMI 5":  {"desc": "Inyector cilindro 5 circuito abierto",     "sistema": "Motor",    "diag": ["Inyector cilindro 5", "Cableado inyector", "Conector", "ECM"]},
    "656 FMI 5":  {"desc": "Inyector cilindro 6 circuito abierto",     "sistema": "Motor",    "diag": ["Inyector cilindro 6", "Cableado inyector", "Conector", "ECM"]},
    "651 FMI 6":  {"desc": "Inyector cilindro 1 cortocircuito",        "sistema": "Motor",    "diag": ["Inyector cilindro 1", "Cableado en masa", "Conector", "ECM"]},
    "652 FMI 6":  {"desc": "Inyector cilindro 2 cortocircuito",        "sistema": "Motor",    "diag": ["Inyector cilindro 2", "Cableado en masa", "Conector", "ECM"]},
    "653 FMI 6":  {"desc": "Inyector cilindro 3 cortocircuito",        "sistema": "Motor",    "diag": ["Inyector cilindro 3", "Cableado en masa", "Conector", "ECM"]},
    "654 FMI 6":  {"desc": "Inyector cilindro 4 cortocircuito",        "sistema": "Motor",    "diag": ["Inyector cilindro 4", "Cableado en masa", "Conector", "ECM"]},
    "655 FMI 6":  {"desc": "Inyector cilindro 5 cortocircuito",        "sistema": "Motor",    "diag": ["Inyector cilindro 5", "Cableado en masa", "Conector", "ECM"]},
    "656 FMI 6":  {"desc": "Inyector cilindro 6 cortocircuito",        "sistema": "Motor",    "diag": ["Inyector cilindro 6", "Cableado en masa", "Conector", "ECM"]},
    "412 FMI 3":  {"desc": "Sensor temperatura EGR cortocircuito",     "sistema": "Motor",    "diag": ["Sensor temperatura EGR", "Cableado", "Conector oxidado", "ECM"]},
    "412 FMI 4":  {"desc": "Sensor temperatura EGR circuito abierto",  "sistema": "Motor",    "diag": ["Sensor temperatura EGR", "Cableado roto", "Conector", "ECM"]},
    "2791 FMI 7": {"desc": "Válvula EGR respuesta incorrecta",         "sistema": "Motor",    "diag": ["Limpiar válvula EGR", "Actuador EGR", "Cableado actuador", "ECM"]},
    "2791 FMI 14":{"desc": "Válvula EGR atascada",                     "sistema": "Motor",    "diag": ["Limpieza válvula EGR urgente", "Depósitos carbonilla", "Sustituir válvula", "Refrigerador EGR"]},
    "1173 FMI 0": {"desc": "Temperatura turbo alta",                   "sistema": "Motor",    "diag": ["Carga excesiva", "Refrigeración turbo", "Aceite turbo", "Sensor temperatura turbo"]},
    "3563 FMI 1": {"desc": "Presión diferencial filtro partículas alta","sistema": "Motor",   "diag": ["Regeneración DPF necesaria", "Filtro DPF obstruido", "Sensor presión diferencial", "Ciclo regeneración"]},
    "3251 FMI 0": {"desc": "Presión diferencial DPF muy alta",         "sistema": "Motor",    "diag": ["DPF colmatado", "Regeneración forzada urgente", "Sustituir DPF", "Sensor presión"]},

    # ===== SCR / ADBLUE =====
    "3364 FMI 1": {"desc": "Eficiencia SCR baja",                      "sistema": "SCR",      "diag": ["Calidad AdBlue", "Inyector AdBlue", "Sensor NOx aguas abajo", "Catalizador SCR"]},
    "3364 FMI 17":{"desc": "Eficiencia SCR muy baja - limitación",     "sistema": "SCR",      "diag": ["AdBlue contaminado", "Inyector AdBlue obstruido", "Sensor NOx", "Catalizador dañado"]},
    "4334 FMI 7": {"desc": "Dosificación AdBlue incorrecta",           "sistema": "SCR",      "diag": ["Bomba AdBlue", "Inyector AdBlue", "Presión sistema AdBlue", "Líneas obstruidas"]},
    "4334 FMI 14":{"desc": "Inyector AdBlue bloqueado",                "sistema": "SCR",      "diag": ["Limpiar inyector AdBlue", "Cristalización urea", "Sustituir inyector", "Líneas AdBlue"]},
    "1761 FMI 1": {"desc": "Nivel AdBlue bajo",                        "sistema": "SCR",      "diag": ["Rellenar AdBlue", "Sensor nivel AdBlue", "Depósito AdBlue", "Cableado sensor"]},
    "1761 FMI 17":{"desc": "Nivel AdBlue crítico - limitación",        "sistema": "SCR",      "diag": ["Rellenar AdBlue inmediatamente", "El vehículo se limitará", "Sensor nivel", "Depósito"]},
    "3516 FMI 3": {"desc": "Sensor NOx aguas arriba cortocircuito",    "sistema": "SCR",      "diag": ["Sensor NOx entrada SCR", "Cableado sensor", "Conector", "SCR ECU"]},
    "3516 FMI 4": {"desc": "Sensor NOx aguas arriba circuito abierto", "sistema": "SCR",      "diag": ["Sensor NOx entrada", "Cableado roto", "Conector", "SCR ECU"]},
    "3490 FMI 3": {"desc": "Sensor NOx aguas abajo cortocircuito",     "sistema": "SCR",      "diag": ["Sensor NOx salida SCR", "Cableado sensor", "Conector", "SCR ECU"]},
    "3490 FMI 4": {"desc": "Sensor NOx aguas abajo circuito abierto",  "sistema": "SCR",      "diag": ["Sensor NOx salida", "Cableado roto", "Conector", "ECU"]},
    "4360 FMI 3": {"desc": "Sensor temperatura SCR cortocircuito",     "sistema": "SCR",      "diag": ["Sensor temperatura SCR", "Cableado", "Conector", "SCR ECU"]},
    "4360 FMI 4": {"desc": "Sensor temperatura SCR circuito abierto",  "sistema": "SCR",      "diag": ["Sensor temperatura SCR", "Cableado roto", "Conector", "ECU"]},
    "5245 FMI 14":{"desc": "Sistema AdBlue congelado",                 "sistema": "SCR",      "diag": ["Calentador depósito AdBlue", "Calentador líneas", "Temperatura ambiente", "Sistema calefacción AdBlue"]},
    "4076 FMI 1": {"desc": "Presión bomba AdBlue baja",                "sistema": "SCR",      "diag": ["Bomba AdBlue averiada", "Filtro bomba obstruido", "Nivel AdBlue", "Líneas obstruidas"]},

    # ===== FRENOS / EBS =====
    "84 FMI 2":   {"desc": "Sensor velocidad rueda señal errática",    "sistema": "Frenos",   "diag": ["Sensor ABS rueda", "Corona ABS dañada", "Entrehierro sensor", "Cableado sensor"]},
    "84 FMI 10":  {"desc": "Sensor velocidad rueda señal anormal",     "sistema": "Frenos",   "diag": ["Sensor ABS", "Corona reluctancia sucia", "Cableado", "ECU ABS/EBS"]},
    "911 FMI 3":  {"desc": "Sensor presión freno cortocircuito",       "sistema": "Frenos",   "diag": ["Sensor presión circuito freno", "Cableado", "Conector", "ECU EBS"]},
    "911 FMI 4":  {"desc": "Sensor presión freno circuito abierto",    "sistema": "Frenos",   "diag": ["Sensor presión freno", "Cableado roto", "Conector", "ECU EBS"]},
    "918 FMI 3":  {"desc": "Sensor presión freno remolque cortocircuito","sistema": "Frenos", "diag": ["Sensor presión remolque", "Cableado", "Conector", "ECU EBS"]},
    "918 FMI 4":  {"desc": "Sensor presión freno remolque abierto",    "sistema": "Frenos",   "diag": ["Sensor presión remolque", "Cableado roto", "Conector", "ECU EBS"]},
    "597 FMI 3":  {"desc": "Interruptor freno cortocircuito",          "sistema": "Frenos",   "diag": ["Switch freno", "Cableado", "Conector", "ECU EBS"]},
    "597 FMI 4":  {"desc": "Interruptor freno circuito abierto",       "sistema": "Frenos",   "diag": ["Switch freno", "Cableado roto", "Ajuste switch", "ECU EBS"]},
    "1085 FMI 7": {"desc": "Módulo EBS respuesta incorrecta",          "sistema": "Frenos",   "diag": ["ECU EBS", "Alimentación ECU", "CAN bus", "Diagnosis EBS"]},
    "563 FMI 2":  {"desc": "Presión aire circuito freno anormal",      "sistema": "Frenos",   "diag": ["Compresor aire", "Secador aire", "Válvula protección circuitos", "Fugas sistema"]},
    "116 FMI 1":  {"desc": "Presión aire depósito baja",               "sistema": "Frenos",   "diag": ["Compresor aire", "Fugas circuito", "Válvula seguridad", "Secador aire"]},
    "116 FMI 17": {"desc": "Presión aire depósito crítica",            "sistema": "Frenos",   "diag": ["Fuga grave", "Compresor averiado", "Válvulas", "Parar vehículo"]},

    # ===== CAJA DE CAMBIOS =====
    "523 FMI 7":  {"desc": "Electroválvula cambio respuesta incorrecta","sistema": "Caja",    "diag": ["Electroválvula cambio", "Presión aire caja", "Instalación eléctrica", "TCU"]},
    "523 FMI 5":  {"desc": "Electroválvula cambio circuito abierto",   "sistema": "Caja",     "diag": ["Electroválvula", "Cableado", "Conector", "TCU"]},
    "523 FMI 6":  {"desc": "Electroválvula cambio cortocircuito",      "sistema": "Caja",     "diag": ["Electroválvula", "Cableado en masa", "Conector", "TCU"]},
    "191 FMI 2":  {"desc": "Sensor velocidad salida caja señal errática","sistema": "Caja",   "diag": ["Sensor velocidad salida", "Corona", "Cableado", "TCU"]},
    "191 FMI 8":  {"desc": "Sensor velocidad salida caja sin señal",   "sistema": "Caja",     "diag": ["Sensor velocidad salida caja", "Cableado", "Corona reluctancia", "TCU"]},
    "127 FMI 1":  {"desc": "Presión aceite caja baja",                 "sistema": "Caja",     "diag": ["Nivel aceite caja", "Bomba aceite caja", "Filtro aceite caja", "Sensor presión"]},
    "177 FMI 0":  {"desc": "Temperatura aceite caja alta",             "sistema": "Caja",     "diag": ["Nivel aceite caja", "Enfriador aceite caja", "Carga excesiva", "Sensor temperatura"]},
    "177 FMI 15": {"desc": "Temperatura aceite caja muy alta",         "sistema": "Caja",     "diag": ["Parar vehículo", "Enfriador caja averiado", "Nivel aceite", "Circulación aceite"]},
    "1482 FMI 7": {"desc": "Actuador selección marcha fallo",          "sistema": "Caja",     "diag": ["Actuador selección", "Presión aire actuador", "Cableado", "TCU"]},
    "1483 FMI 7": {"desc": "Actuador enganche marcha fallo",           "sistema": "Caja",     "diag": ["Actuador enganche", "Presión aire", "Sincronizadores", "TCU"]},
    "574 FMI 3":  {"desc": "Interruptor punto muerto cortocircuito",   "sistema": "Caja",     "diag": ["Switch punto muerto", "Cableado", "Conector", "TCU"]},
    "574 FMI 4":  {"desc": "Interruptor punto muerto circuito abierto","sistema": "Caja",     "diag": ["Switch punto muerto", "Cableado roto", "Ajuste switch", "TCU"]},
    "1716 FMI 9": {"desc": "Pérdida comunicación CAN con TCU",         "sistema": "Caja",     "diag": ["CAN bus", "Resistencias terminación CAN", "Cableado CAN", "TCU alimentación"]},

    # ===== RADAR / ADAS =====
    "5298 FMI 2": {"desc": "Señal radar errática",                     "sistema": "Radar",    "diag": ["Limpieza frontal radar", "Calibración radar", "Golpe en parachoques", "Módulo radar"]},
    "5298 FMI 9": {"desc": "Pérdida comunicación módulo radar",        "sistema": "Radar",    "diag": ["CAN bus ADAS", "Alimentación módulo radar", "Cableado", "Módulo radar"]},
    "5298 FMI 14":{"desc": "Radar bloqueado / obstruido",              "sistema": "Radar",    "diag": ["Limpiar rejilla frontal", "Hielo o suciedad", "Daño físico", "Recalibrar"]},
    "5300 FMI 7": {"desc": "Sistema ACC respuesta incorrecta",         "sistema": "Radar",    "diag": ["Calibración ACC", "Módulo radar", "Sensor velocidad", "Parámetros sistema"]},
    "5301 FMI 9": {"desc": "Pérdida comunicación ADAS",                "sistema": "Radar",    "diag": ["CAN bus ADAS", "Módulo ADAS", "Cableado", "Alimentación sistema"]},
    "5302 FMI 2": {"desc": "Cámara ADAS señal errática",               "sistema": "Radar",    "diag": ["Limpiar parabrisas zona cámara", "Calibración cámara", "Módulo cámara", "Cableado"]},

    # ===== ELÉCTRICO / CAN =====
    "639 FMI 9":  {"desc": "Pérdida comunicación CAN bus",             "sistema": "Eléctrico","diag": ["Resistencias terminación CAN 120Ω", "Cableado CAN bus", "Módulos en cortocircuito", "Diagnosis general"]},
    "639 FMI 14": {"desc": "Error CAN bus general",                    "sistema": "Eléctrico","diag": ["Cortocircuito CAN", "Nodo defectuoso", "Cableado", "Alimentaciones módulos"]},
    "168 FMI 1":  {"desc": "Tensión batería baja",                     "sistema": "Eléctrico","diag": ["Batería descargada", "Alternador", "Consumo parásito", "Bornes batería"]},
    "168 FMI 17": {"desc": "Tensión batería crítica",                  "sistema": "Eléctrico","diag": ["Batería averiada", "Alternador averiado", "Cableado masa", "Bornes oxidados"]},
    "168 FMI 0":  {"desc": "Tensión batería alta",                     "sistema": "Eléctrico","diag": ["Regulador alternador", "Alternador", "Sensor tensión", "Cableado"]},
    "1569 FMI 31":{"desc": "Limitación motor por emisiones",           "sistema": "Eléctrico","diag": ["Sistema SCR defectuoso", "AdBlue nivel crítico", "Fallo NOx reiterado", "Diagnosis completa"]},
    "629 FMI 12": {"desc": "ECM fallo interno",                        "sistema": "Eléctrico","diag": ["Alimentación ECM", "Masa ECM", "Actualizar software ECM", "Sustituir ECM"]},
    "629 FMI 14": {"desc": "ECM advertencia interna",                  "sistema": "Eléctrico","diag": ["Alimentación ECM", "Temperatura ECM", "Software ECM", "Diagnosis"]},

    # ===== EMBRAGUE =====
    "1031 FMI 7": {"desc": "Actuador embrague respuesta incorrecta",   "sistema": "Embrague", "diag": ["Actuador embrague", "Presión aire actuador", "Desgaste disco embrague", "Calibración embrague"]},
    "1031 FMI 5": {"desc": "Actuador embrague circuito abierto",       "sistema": "Embrague", "diag": ["Cableado actuador", "Conector", "Actuador averiado", "TCU"]},
    "1031 FMI 14":{"desc": "Embrague patinando",                       "sistema": "Embrague", "diag": ["Desgaste disco embrague", "Aceite en embrague", "Calibración", "Actuador"]},
    "1033 FMI 7": {"desc": "Sensor posición embrague incorrecto",      "sistema": "Embrague", "diag": ["Sensor posición embrague", "Cableado sensor", "Calibración sensor", "TCU"]},
}

# =====================================================================
# SÍNTOMAS
# =====================================================================
SINTOMAS = {
    "humo blanco":    "Posible inyector averiado / junta culata / pérdida de compresión",
    "humo negro":     "Exceso combustible: inyectores / turbo / EGR bloqueado / MAF",
    "humo azul":      "Consumo aceite: sellos válvulas / segmentos / turbo",
    "falta potencia": "Revisar: turbo / filtro aire / EGR / sistema combustible",
    "no arranca":     "Revisar: batería / motor arranque / combustible / sensor régimen",
    "sin arranque":   "Revisar: batería / precalentamiento / combustible / ECM",
    "tirones":        "Revisar: inyección / sensores MAF-MAP / filtro aire",
    "consumo alto":   "Revisar: MAF / inyección / turbo / EGR",
    "fallo adblue":   "Revisar: sistema SCR / inyector AdBlue / bomba / sensor NOx",
    "ruido motor":    "Revisar: nivel aceite / presión aceite / distribución / cojinetes",
    "frenos duros":   "Revisar: servofreno / presión aire / válvulas freno",
    "embrague":       "Revisar: actuador embrague / desgaste disco / hidráulico",
    "vibración":      "Revisar: soportes motor / cardán / ruedas / embrague",
    "no cambia":      "Revisar: TCU / actuadores caja / presión aire / sensor posición",
    "caliente":       "Revisar: nivel refrigerante / termostato / bomba agua / radiador",
}

# =====================================================================
# STATS
# =====================================================================
def cargar_stats():
    base = {
        "usos": 0, "usuarios": [],
        "facil_si": 0, "facil_no": 0,
        "intuitivo_si": 0, "intuitivo_no": 0,
        "util_si": 0, "util_no": 0,
        "codigos_consultados": [],
        "ingresos_inicio": 0,
        "ingresos_sintoma": 0,
        "ingresos_codigo": 0,
    }
    if not os.path.exists(STATS_FILE):
        return base
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
    except:
        return base
    for k in base:
        if k not in data:
            data[k] = base[k]
    return data

def guardar_stats(data):
    with open(STATS_FILE, "w") as f:
        json.dump(data, f)

stats = cargar_stats()

# =====================================================================
# VERIFICAR PAGO STRIPE
# =====================================================================
def verificar_pago(email, link):
    try:
        link_id = link.split("/")[-1]
        sesiones = stripe.checkout.Session.list(limit=100)
        for sesion in sesiones.auto_paging_iter():
            if (sesion.status == "complete" and
                sesion.customer_details and
                sesion.customer_details.email and
                sesion.customer_details.email.lower() == email.lower() and
                sesion.payment_link and
                sesion.payment_link == link_id):
                return True
        return False
    except Exception:
        return False

# =====================================================================
# BOTONES
# =====================================================================
def btn_inicio(user_id=None):
    botones = [
        [InlineKeyboardButton("🚀 INICIAR — 5€", callback_data="pagar_inicio")],
        [InlineKeyboardButton("🧠 Síntomas — 10€", callback_data="pagar_sintoma")],
        [InlineKeyboardButton("🔍 Código error — 30€", callback_data="pagar_codigo")],
    ]
    if str(user_id) == str(ADMIN_ID):
        botones.append([InlineKeyboardButton("📊 Estadísticas", callback_data="stats")])
    return InlineKeyboardMarkup(botones)

def btn_si_no(base):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Sí", callback_data=f"{base}_si"),
         InlineKeyboardButton("No", callback_data=f"{base}_no")]
    ])

def btn_tipo():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Motor", callback_data="motor")],
        [InlineKeyboardButton("EBS / Frenos", callback_data="frenos")],
        [InlineKeyboardButton("SCR", callback_data="scr")],
        [InlineKeyboardButton("Radar", callback_data="radar")],
        [InlineKeyboardButton("Caja cambios", callback_data="caja")]
    ])

def btn_color():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟡 Amarillo", callback_data="amarillo"),
         InlineKeyboardButton("🔴 Rojo", callback_data="rojo")]
    ])

def btn_confirmar_pago(tipo):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ya he pagado", callback_data=f"confirmar_{tipo}")],
        [InlineKeyboardButton("🔙 Volver", callback_data="volver")]
    ])

# =====================================================================
# START
# =====================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    user_id = update.effective_user.id
    stats["usos"] += 1
    if str(user_id) not in stats["usuarios"]:
        stats["usuarios"].append(str(user_id))
    guardar_stats(stats)
    context.user_data.clear()
    await update.effective_message.reply_text("Iniciando...", reply_markup=ReplyKeyboardRemove())
    await update.effective_message.reply_text(
        "🚛 *Bot Diagnóstico IVECO*\n\nSelecciona el servicio:",
        parse_mode="Markdown",
        reply_markup=btn_inicio(user_id)
    )

# =====================================================================
# ENCUESTA
# =====================================================================
async def lanzar_encuesta(message):
    await message.reply_text("📋 3 preguntas rápidas para valorar el bot.")
    await message.reply_text("¿Le ha resultado fácil?", reply_markup=btn_si_no("enc1"))

# =====================================================================
# BOTONES
# =====================================================================
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    q = update.callback_query
    await q.answer()
    d = q.data
    user_id = update.effective_user.id

    if d == "pagar_inicio":
        context.user_data.clear()
        context.user_data["servicio"] = "inicio"
        await q.edit_message_text(
            "🚀 *Consulta INICIO — 5€*\n\n"
            "1️⃣ Realiza el pago aquí:\n" + LINK_INICIO +
            "\n\n2️⃣ Usa el *mismo email* con el que pagas\n\n"
            "3️⃣ Pulsa ✅ *Ya he pagado*",
            parse_mode="Markdown",
            reply_markup=btn_confirmar_pago("inicio")
        )

    elif d == "pagar_sintoma":
        context.user_data.clear()
        context.user_data["servicio"] = "sintoma"
        await q.edit_message_text(
            "🧠 *Consulta SÍNTOMA — 10€*\n\n"
            "1️⃣ Realiza el pago aquí:\n" + LINK_SINTOMA +
            "\n\n2️⃣ Usa el *mismo email* con el que pagas\n\n"
            "3️⃣ Pulsa ✅ *Ya he pagado*",
            parse_mode="Markdown",
            reply_markup=btn_confirmar_pago("sintoma")
        )

    elif d == "pagar_codigo":
        context.user_data.clear()
        context.user_data["servicio"] = "codigo"
        await q.edit_message_text(
            "🔍 *Consulta CÓDIGO ERROR — 30€*\n\n"
            "1️⃣ Realiza el pago aquí:\n" + LINK_CODIGO +
            "\n\n2️⃣ Usa el *mismo email* con el que pagas\n\n"
            "3️⃣ Pulsa ✅ *Ya he pagado*",
            parse_mode="Markdown",
            reply_markup=btn_confirmar_pago("codigo")
        )

    elif d.startswith("confirmar_"):
        tipo = d.split("_")[1]
        context.user_data["esperando_email"] = tipo
        await q.edit_message_text(
            "✉️ Introduce el *email* con el que realizaste el pago:",
            parse_mode="Markdown"
        )

    elif d == "inicio_verificado":
        await q.edit_message_text("¿Testigo en cuadro?", reply_markup=btn_si_no("testigo"))

    elif d == "testigo_si":
        await q.edit_message_text("Tipo de testigo:", reply_markup=btn_tipo())

    elif d == "testigo_no":
        context.user_data["modo_sintomas_libre"] = True
        await q.edit_message_text(
            "Describe el síntoma del vehículo:\n\n"
            "_Ej: humo blanco, falta potencia, no arranca, tirones..._",
            parse_mode="Markdown"
        )

    elif d in ["motor", "frenos", "scr", "radar", "caja"]:
        context.user_data["tipo"] = d
        await q.edit_message_text("Color del testigo:", reply_markup=btn_color())

    elif d == "amarillo" and context.user_data.get("tipo") == "motor":
        await q.edit_message_text("¿Vehículo limitado?", reply_markup=btn_si_no("lim"))

    elif d == "lim_si":
        await q.edit_message_text("⚠️ Posible fallo sistema SCR (vehículo limitado)")
        await lanzar_encuesta(q.message)

    elif d == "lim_no":
        await q.edit_message_text("🔧 Revisar en taller")
        await lanzar_encuesta(q.message)

    elif d == "rojo" and context.user_data.get("tipo") == "motor":
        await q.edit_message_text("🔴 FALLO GRAVE → taller urgente")
        await lanzar_encuesta(q.message)

    elif d == "amarillo" and context.user_data.get("tipo") == "frenos":
        await q.edit_message_text("⚠️ Posible fallo sensores EBS / sensores velocidad ruedas")
        await lanzar_encuesta(q.message)

    elif d == "rojo" and context.user_data.get("tipo") == "frenos":
        await q.edit_message_text("🔴 Pérdida de aire / fallo eléctrico")
        await lanzar_encuesta(q.message)

    elif d == "amarillo" and context.user_data.get("tipo") == "scr":
        await q.edit_message_text("⚠️ Posible regeneración en curso")
        await lanzar_encuesta(q.message)

    elif d == "rojo" and context.user_data.get("tipo") == "scr":
        await q.edit_message_text("🔴 Fallo sistema SCR / módulo AdBlue bloqueado / fallo inyector / fuga AdBlue")
        await lanzar_encuesta(q.message)

    elif d == "amarillo" and context.user_data.get("tipo") == "radar":
        await q.edit_message_text("⚠️ Fallo calibración / radar desalineado / radar golpeado")
        await lanzar_encuesta(q.message)

    elif d == "rojo" and context.user_data.get("tipo") == "radar":
        await q.edit_message_text("🔴 Defecto radar / fallo eléctrico")
        await lanzar_encuesta(q.message)

    elif d == "amarillo" and context.user_data.get("tipo") == "caja":
        await q.edit_message_text("⚠️ Fallo eléctrico / fallo electroválvulas")
        await lanzar_encuesta(q.message)

    elif d == "rojo" and context.user_data.get("tipo") == "caja":
        await q.edit_message_text("🔴 Fuga de aire / bloqueo centralita")
        await lanzar_encuesta(q.message)

    elif d == "stats":
        if str(user_id) != str(ADMIN_ID):
            await q.answer("⛔ No autorizado", show_alert=True)
            return
        from collections import Counter
        codigos = stats.get("codigos_consultados", [])
        top = ""
        if codigos:
            top3 = Counter(codigos).most_common(3)
            top = "\n\n🔥 *Top códigos:*\n" + "\n".join([f"• {c} → {n} veces" for c, n in top3])
        ingresos = (stats["ingresos_inicio"] * 5 +
                    stats["ingresos_sintoma"] * 10 +
                    stats["ingresos_codigo"] * 30)
        texto = (
            f"📊 *Estadísticas*\n\n"
            f"Usos totales: {stats['usos']}\n"
            f"Usuarios únicos: {len(stats['usuarios'])}\n"
            f"Códigos consultados: {len(codigos)}\n\n"
            f"💶 *Ingresos estimados: {ingresos}€*\n"
            f"  Inicio: {stats['ingresos_inicio']} consultas\n"
            f"  Síntoma: {stats['ingresos_sintoma']} consultas\n"
            f"  Código: {stats['ingresos_codigo']} consultas\n\n"
            f"📋 *Encuestas:*\n"
            f"¿Fácil?      ✅ {stats['facil_si']}  ❌ {stats['facil_no']}\n"
            f"¿Intuitivo?  ✅ {stats['intuitivo_si']}  ❌ {stats['intuitivo_no']}\n"
            f"¿Útil?       ✅ {stats['util_si']}  ❌ {stats['util_no']}"
            f"{top}"
        )
        await q.edit_message_text(texto, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="volver")]]))

    elif d == "volver":
        context.user_data.clear()
        await q.edit_message_text("Selecciona el servicio:", reply_markup=btn_inicio(user_id))

    elif d.startswith("enc1"):
        stats["facil_si" if "si" in d else "facil_no"] += 1
        guardar_stats(stats)
        await q.edit_message_text("¿Le ha parecido intuitivo?", reply_markup=btn_si_no("enc2"))

    elif d.startswith("enc2"):
        stats["intuitivo_si" if "si" in d else "intuitivo_no"] += 1
        guardar_stats(stats)
        await q.edit_message_text("¿Le ha ayudado?", reply_markup=btn_si_no("enc3"))

    elif d.startswith("enc3"):
        stats["util_si" if "si" in d else "util_no"] += 1
        guardar_stats(stats)
        await q.edit_message_text(
            "✅ Gracias por su valoración.\n\nPara una nueva consulta vuelve a empezar:",
            reply_markup=btn_inicio(user_id)
        )

# =====================================================================
# TEXTO
# =====================================================================
async def texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    user_id = update.effective_user.id
    texto_user = update.message.text.strip()

    if context.user_data.get("esperando_email"):
        tipo = context.user_data.pop("esperando_email")
        email = texto_user.strip().lower()
        link = {"inicio": LINK_INICIO, "sintoma": LINK_SINTOMA, "codigo": LINK_CODIGO}[tipo]

        await update.message.reply_text("🔄 Verificando pago...")
        pagado = verificar_pago(email, link)

        if pagado:
            context.user_data["pagado"] = tipo
            context.user_data["email"] = email

            if tipo == "inicio":
                stats["ingresos_inicio"] += 1
                guardar_stats(stats)
                await update.message.reply_text(
                    "✅ Pago verificado. Tienes 1 consulta disponible.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("▶️ Continuar", callback_data="inicio_verificado")]
                    ])
                )
            elif tipo == "sintoma":
                stats["ingresos_sintoma"] += 1
                guardar_stats(stats)
                context.user_data["modo_sintomas"] = True
                await update.message.reply_text(
                    "✅ Pago verificado. Tienes 1 consulta disponible.\n\n"
                    "🧠 Describe el síntoma:\n"
                    "_Ej: humo blanco, falta potencia, no arranca..._",
                    parse_mode="Markdown"
                )
            elif tipo == "codigo":
                stats["ingresos_codigo"] += 1
                guardar_stats(stats)
                context.user_data["modo_codigo"] = True
                await update.message.reply_text(
                    "✅ Pago verificado. Tienes 1 consulta disponible.\n\n"
                    "🔍 Introduce el código de error:\n"
                    "_Formato: SPN FMI número (ej: 111 FMI 1)_",
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(
                "❌ No se encontró el pago con ese email.\n\n"
                "Comprueba que:\n"
                "• El email es correcto\n"
                "• El pago está completado\n"
                "• Espera unos segundos y reintenta",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Reintentar", callback_data=f"confirmar_{tipo}")],
                    [InlineKeyboardButton("🔙 Volver", callback_data="volver")]
                ])
            )
        return

    if context.user_data.get("modo_codigo"):
        busqueda = texto_user.upper().strip()
        if busqueda in CODIGOS:
            resultados = [(busqueda, CODIGOS[busqueda])]
        else:
            resultados = [(k, v) for k, v in CODIGOS.items() if busqueda in k]

        if not resultados:
            await update.message.reply_text(
                "❌ Código no encontrado.\n\n"
                "Formato correcto: *SPN FMI número*\n"
                "Ejemplo: `111 FMI 1`\n\n"
                "Vuelve a introducir el código:",
                parse_mode="Markdown"
            )
            return

        if len(resultados) == 1:
            context.user_data["modo_codigo"] = False
            clave, data = resultados[0]
            stats["codigos_consultados"].append(clave)
            guardar_stats(stats)
            diag = "\n".join([f"  • {x}" for x in data["diag"]])
            msg = (
                f"🔍 *{clave}*\n"
                f"🏷 Sistema: {data['sistema']}\n"
                f"📋 {data['desc']}\n\n"
                f"🔧 *Pasos diagnóstico:*\n{diag}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
            await lanzar_encuesta(update.message)
        else:
            lista = "\n".join([f"• *{k}* — {v['desc']}" for k, v in resultados[:8]])
            await update.message.reply_text(
                f"🔎 {len(resultados)} coincidencias:\n\n{lista}\n\n"
                "Introduce el código *completo*. Ejemplo: `111 FMI 1`",
                parse_mode="Markdown"
            )
        return

    if context.user_data.get("modo_sintomas") or context.user_data.get("modo_sintomas_libre"):
        modo = "modo_sintomas" if context.user_data.get("modo_sintomas") else "modo_sintomas_libre"
        context.user_data[modo] = False
        texto_lower = texto_user.lower()
        encontrado = False
        for s, resp in SINTOMAS.items():
            if s in texto_lower:
                await update.message.reply_text(
                    f"🧠 *{s.capitalize()}*\n\n🔧 {resp}",
                    parse_mode="Markdown"
                )
                encontrado = True
                break
        if not encontrado:
            await update.message.reply_text(
                "❌ Síntoma no reconocido.\n\n"
                "Prueba con: _humo blanco, humo negro, falta potencia, no arranca, tirones, consumo alto, fallo adblue..._",
                parse_mode="Markdown"
            )
        await lanzar_encuesta(update.message)
        return

    await update.message.reply_text("Selecciona el servicio:", reply_markup=btn_inicio(user_id))

# =====================================================================
# APP
# =====================================================================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(botones))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto))

print("✅ Bot IVECO OK 🚛")
app.run_polling(drop_pending_updates=True)
