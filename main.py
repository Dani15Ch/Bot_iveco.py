import json
import os
import time
import threading
import stripe
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# =====================================================================
# CONFIGURACIÓN
# =====================================================================
TOKEN          = os.environ["TELEGRAM_TOKEN"]
ADMIN_ID       = int(os.environ["ADMIN_ID"])
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
RENDER_URL     = os.environ["RENDER_URL"]

LINK_INICIO  = "https://buy.stripe.com/14AbJ13XUfU8fwv8R99fW00"  # 5€
LINK_SINTOMA = "https://buy.stripe.com/aFabJ1cuqdM04RRgjB9fW01"  # 10€
LINK_CODIGO  = "https://buy.stripe.com/bJe8wPami9vKfwv3wP9fW02"  # 30€

LINK_ID_INICIO  = LINK_INICIO.split("/")[-1]
LINK_ID_SINTOMA = LINK_SINTOMA.split("/")[-1]
LINK_ID_CODIGO  = LINK_CODIGO.split("/")[-1]

STATS_FILE    = "stats.json"
PAYMENTS_FILE = "payments.json"

# =====================================================================
# PERSISTENCIA
# =====================================================================
def load_json(file, default):
    if not os.path.exists(file):
        return default
    try:
        with open(file) as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

payments = load_json(PAYMENTS_FILE, {})
stats = load_json(STATS_FILE, {
    "usos": 0, "usuarios": [],
    "facil_si": 0, "facil_no": 0,
    "intuitivo_si": 0, "intuitivo_no": 0,
    "util_si": 0, "util_no": 0,
    "inicio_consultas": 0,
    "sintoma_consultas": 0,
    "codigo_consultas": 0,
    "codigos_consultados": {},
    "sintomas_consultados": {},
    "sistemas_consultados": {},
    "ingresos_inicio": 0,
    "ingresos_sintoma": 0,
    "ingresos_codigo": 0,
})

# =====================================================================
# VERIFICAR PAGO STRIPE
# =====================================================================
def verificar_pago(email, tipo):
    email = email.lower().strip()
    ahora = time.time()
    for session_id, data in payments.items():
        if data.get("email") != email:
            continue
        if data.get("tipo") != tipo:
            continue
        if data.get("usado"):
            continue
        if ahora - data.get("ts", 0) > 3600:
            continue
        payments[session_id]["usado"] = True
        save_json(PAYMENTS_FILE, payments)
        return True
    return False

# =====================================================================
# SERVIDOR HTTP — Webhook Stripe + Telegram + Keep-alive
# =====================================================================
_application = None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot IVECO activo")

    def do_POST(self):
        parsed = urlparse(self.path)
        length  = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length)

        if parsed.path == "/stripe":
            sig = self.headers.get("Stripe-Signature", "")
            try:
                event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
            except Exception:
                self.send_response(400)
                self.end_headers()
                return

            if event["type"] == "checkout.session.completed":
                session    = event["data"]["object"]
                session_id = session.get("id")
                email      = session.get("customer_details", {}).get("email", "").lower()
                link_id    = session.get("payment_link", "")
                ts         = session.get("created", time.time())

                if email and session_id and session_id not in payments:
                    if link_id == LINK_ID_INICIO:
                        tipo = "inicio"
                    elif link_id == LINK_ID_SINTOMA:
                        tipo = "sintoma"
                    elif link_id == LINK_ID_CODIGO:
                        tipo = "codigo"
                    else:
                        self.send_response(200)
                        self.end_headers()
                        return

                    payments[session_id] = {
                        "email": email,
                        "tipo":  tipo,
                        "ts":    ts,
                        "usado": False,
                    }
                    save_json(PAYMENTS_FILE, payments)

            self.send_response(200)
            self.end_headers()
            return

        if parsed.path == f"/{TOKEN}":
            import asyncio
            try:
                update_data = json.loads(payload.decode("utf-8"))
                upd = Update.de_json(update_data, _application.bot)
                asyncio.run_coroutine_threadsafe(
                    _application.process_update(upd),
                    _loop
                )
            except Exception as e:
                print("Webhook Telegram error:", e)
            self.send_response(200)
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass

_loop = None

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# =====================================================================
# TRADUCCIONES — 6 idiomas
# =====================================================================
TEXTOS = {
    "es": {
        "bienvenida": "🚛 *Bot Diagnóstico IVECO*\n\nSelecciona el servicio:",
        "iniciar": "🚀 INICIAR — 5€", "sintomas": "🧠 Síntomas — 10€", "codigo": "🔍 Código error — 30€",
        "estadisticas": "📊 Estadísticas", "testigo": "¿Testigo encendido en el cuadro?",
        "si": "Sí", "no": "No", "tipo_testigo": "Tipo de testigo:",
        "motor": "Motor", "frenos": "EBS / Frenos", "scr": "SCR / AdBlue",
        "dpf": "DPF / Emisiones", "caja": "Caja cambios",
        "color_testigo": "Color del testigo:", "amarillo": "🟡 Amarillo", "rojo": "🔴 Rojo",
        "limitado": "¿Vehículo limitado?",
        "pagar_inicio": "🚀 *Consulta INICIO — 5€*\n\n1️⃣ Paga aquí:\n{link}\n\n2️⃣ Mismo *email*\n\n3️⃣ Pulsa ✅ *Ya he pagado*",
        "pagar_sintoma": "🧠 *Consulta SÍNTOMA — 10€*\n\n1️⃣ Paga aquí:\n{link}\n\n2️⃣ Mismo *email*\n\n3️⃣ Pulsa ✅ *Ya he pagado*",
        "pagar_codigo": "🔍 *Consulta CÓDIGO — 30€*\n\n1️⃣ Paga aquí:\n{link}\n\n2️⃣ Mismo *email*\n\n3️⃣ Pulsa ✅ *Ya he pagado*",
        "ya_pagado": "✅ Ya he pagado", "volver": "🔙 Volver",
        "pedir_email": "✉️ Introduce el *email* con el que pagaste:",
        "verificando": "🔄 Verificando pago...",
        "pago_ok": "✅ Pago verificado. Tienes 1 consulta disponible.",
        "continuar": "▶️ Continuar",
        "pago_error": "❌ Pago no válido, ya usado o caducado.\n\nComprueba:\n• Email correcto\n• Pago en la última hora\n• No usado previamente\n• Espera y reintenta",
        "reintentar": "🔄 Reintentar",
        "intro_codigo": "🔍 Introduce el código:\n_Formato: SPN FMI número (ej: 111 FMI 1)_",
        "intro_sintoma": "🧠 Describe el síntoma:\n\n_Ej: humo blanco, falta potencia, no arranca..._",
        "codigo_no_encontrado": "❌ Código no encontrado.\n\nFormato: *SPN FMI número*\nEj: `111 FMI 1`\n\nVuelve a introducir:",
        "sintoma_no_encontrado": "❌ Síntoma no reconocido.\n\nPrueba: _humo blanco, humo negro, falta potencia, no arranca, tirones, fallo adblue..._",
        "sistema": "🏷 Sistema", "pasos": "🔧 *Pasos diagnóstico:*",
        "enc_inicio": "📋 3 preguntas rápidas para valorar el bot.",
        "enc1": "¿Le ha resultado fácil?", "enc2": "¿Le ha parecido intuitivo?", "enc3": "¿Le ha ayudado?",
        "enc_fin": "✅ Gracias.\n\nPara nueva consulta vuelve a empezar:",
        "motor_amarillo_lim_si": "⚠️ Posible fallo SCR (limitado) — conectar Diagnosis Iveco",
        "motor_amarillo_lim_no": "🔧 Revisar en taller — conectar Diagnosis Iveco",
        "motor_rojo": "🔴 FALLO GRAVE → parar y llamar asistencia IVECO",
        "frenos_amarillo": "⚠️ Posible fallo sensor ABS / EBS / velocidad rueda",
        "frenos_rojo": "🔴 Fallo grave EBS — pérdida presión aire / fallo eléctrico",
        "scr_amarillo": "⚠️ AdBlue bajo / regeneración SCR / sensor NOx",
        "scr_rojo": "🔴 Fallo SCR — inyector AdBlue / bomba / catalizador / contaminado",
        "dpf_amarillo": "⚠️ Regeneración DPF necesaria — 30min carretera >1500rpm",
        "dpf_rojo": "🔴 DPF colmatado — regeneración forzada urgente",
        "caja_amarillo": "⚠️ Fallo eléctrico caja / solenoide / sensor posición",
        "caja_rojo": "🔴 Fallo grave caja — revisar TCU / aceite / actuadores",
        "menu": "Selecciona el servicio:",
        "coincidencias": "🔎 {n} coincidencias:\n\n{lista}\n\nCódigo *completo*. Ej: `111 FMI 1`",
        "acceso_admin": "🔑 Acceso administrador — consulta gratuita",
    },
    "en": {
        "bienvenida": "🚛 *IVECO Diagnostic Bot*\n\nSelect a service:",
        "iniciar": "🚀 START — 5€", "sintomas": "🧠 Symptoms — 10€", "codigo": "🔍 Error code — 30€",
        "estadisticas": "📊 Statistics", "testigo": "Is there a warning light?",
        "si": "Yes", "no": "No", "tipo_testigo": "Type of warning light:",
        "motor": "Engine", "frenos": "EBS / Brakes", "scr": "SCR / AdBlue",
        "dpf": "DPF / Emissions", "caja": "Gearbox",
        "color_testigo": "Warning light color:", "amarillo": "🟡 Yellow", "rojo": "🔴 Red",
        "limitado": "Is the vehicle limited?",
        "pagar_inicio": "🚀 *START Consultation — 5€*\n\n1️⃣ Pay here:\n{link}\n\n2️⃣ Same *email*\n\n3️⃣ Press ✅ *I have paid*",
        "pagar_sintoma": "🧠 *SYMPTOM Consultation — 10€*\n\n1️⃣ Pay here:\n{link}\n\n2️⃣ Same *email*\n\n3️⃣ Press ✅ *I have paid*",
        "pagar_codigo": "🔍 *ERROR CODE Consultation — 30€*\n\n1️⃣ Pay here:\n{link}\n\n2️⃣ Same *email*\n\n3️⃣ Press ✅ *I have paid*",
        "ya_pagado": "✅ I have paid", "volver": "🔙 Back",
        "pedir_email": "✉️ Enter the *email* used for payment:",
        "verificando": "🔄 Verifying...", "pago_ok": "✅ Payment verified. 1 consultation available.",
        "continuar": "▶️ Continue",
        "pago_error": "❌ Payment not valid, already used or expired.\n\nCheck:\n• Correct email\n• Payment within last hour\n• Not previously used\n• Wait and retry",
        "reintentar": "🔄 Retry",
        "intro_codigo": "🔍 Enter the error code:\n_Format: SPN FMI number (e.g: 111 FMI 1)_",
        "intro_sintoma": "🧠 Describe the symptom:\n\n_E.g: white smoke, lack of power, won't start..._",
        "codigo_no_encontrado": "❌ Code not found.\n\nFormat: *SPN FMI number*\nE.g: `111 FMI 1`\n\nEnter again:",
        "sintoma_no_encontrado": "❌ Symptom not recognized.\n\nTry: _white smoke, black smoke, lack of power, won't start..._",
        "sistema": "🏷 System", "pasos": "🔧 *Diagnostic steps:*",
        "enc_inicio": "📋 3 quick questions to rate the bot.",
        "enc1": "Was it easy?", "enc2": "Was it intuitive?", "enc3": "Did it help?",
        "enc_fin": "✅ Thank you.\n\nFor a new consultation start again:",
        "motor_amarillo_lim_si": "⚠️ Possible SCR fault (limited) — connect IVECO Diagnosis",
        "motor_amarillo_lim_no": "🔧 Workshop — connect IVECO Diagnosis",
        "motor_rojo": "🔴 SERIOUS FAULT → stop and call IVECO assistance",
        "frenos_amarillo": "⚠️ Possible ABS / EBS sensor fault",
        "frenos_rojo": "🔴 Serious EBS fault — air loss / electrical fault",
        "scr_amarillo": "⚠️ Low AdBlue / SCR regeneration / NOx sensor",
        "scr_rojo": "🔴 SCR fault — AdBlue injector / pump / catalyst / contaminated",
        "dpf_amarillo": "⚠️ DPF regeneration needed — 30min motorway >1500rpm",
        "dpf_rojo": "🔴 DPF clogged — urgent forced regeneration",
        "caja_amarillo": "⚠️ Gearbox electrical fault / solenoid / position sensor",
        "caja_rojo": "🔴 Serious gearbox fault — check TCU / oil / actuators",
        "menu": "Select a service:",
        "coincidencias": "🔎 {n} matches:\n\n{lista}\n\nFull code. E.g: `111 FMI 1`",
        "acceso_admin": "🔑 Admin access — free consultation",
    },
    "fr": {
        "bienvenida": "🚛 *Bot Diagnostic IVECO*\n\nSélectionnez un service:",
        "iniciar": "🚀 DÉMARRER — 5€", "sintomas": "🧠 Symptômes — 10€", "codigo": "🔍 Code erreur — 30€",
        "estadisticas": "📊 Statistiques", "testigo": "Y a-t-il un voyant allumé?",
        "si": "Oui", "no": "Non", "tipo_testigo": "Type de voyant:",
        "motor": "Moteur", "frenos": "EBS / Freins", "scr": "SCR / AdBlue",
        "dpf": "DPF / Émissions", "caja": "Boîte de vitesses",
        "color_testigo": "Couleur du voyant:", "amarillo": "🟡 Jaune", "rojo": "🔴 Rouge",
        "limitado": "Le véhicule est-il limité?",
        "pagar_inicio": "🚀 *Consultation DÉMARRAGE — 5€*\n\n1️⃣ Payez ici:\n{link}\n\n2️⃣ Même *email*\n\n3️⃣ Appuyez ✅ *J'ai payé*",
        "pagar_sintoma": "🧠 *Consultation SYMPTÔME — 10€*\n\n1️⃣ Payez ici:\n{link}\n\n2️⃣ Même *email*\n\n3️⃣ Appuyez ✅ *J'ai payé*",
        "pagar_codigo": "🔍 *Consultation CODE — 30€*\n\n1️⃣ Payez ici:\n{link}\n\n2️⃣ Même *email*\n\n3️⃣ Appuyez ✅ *J'ai payé*",
        "ya_pagado": "✅ J'ai payé", "volver": "🔙 Retour",
        "pedir_email": "✉️ Entrez l'*email* du paiement:",
        "verificando": "🔄 Vérification...", "pago_ok": "✅ Paiement vérifié. 1 consultation disponible.",
        "continuar": "▶️ Continuer",
        "pago_error": "❌ Paiement invalide, déjà utilisé ou expiré.",
        "reintentar": "🔄 Réessayer",
        "intro_codigo": "🔍 Entrez le code:\n_Format: SPN FMI numéro (ex: 111 FMI 1)_",
        "intro_sintoma": "🧠 Décrivez le symptôme:\n\n_Ex: fumée blanche, manque puissance..._",
        "codigo_no_encontrado": "❌ Code non trouvé.\n\nFormat: *SPN FMI numéro*\nEx: `111 FMI 1`",
        "sintoma_no_encontrado": "❌ Symptôme non reconnu.",
        "sistema": "🏷 Système", "pasos": "🔧 *Étapes diagnostic:*",
        "enc_inicio": "📋 3 questions pour évaluer.", "enc1": "Facile?", "enc2": "Intuitif?", "enc3": "Utile?",
        "enc_fin": "✅ Merci.\n\nPour nouvelle consultation recommencez:",
        "motor_amarillo_lim_si": "⚠️ Possible défaillance SCR (limité) — IVECO Diagnosis",
        "motor_amarillo_lim_no": "🔧 Atelier — IVECO Diagnosis",
        "motor_rojo": "🔴 DÉFAILLANCE GRAVE → arrêter et appeler IVECO",
        "frenos_amarillo": "⚠️ Possible défaillance ABS / EBS",
        "frenos_rojo": "🔴 Défaillance grave EBS",
        "scr_amarillo": "⚠️ AdBlue bas / régénération SCR / NOx",
        "scr_rojo": "🔴 Défaillance SCR — injecteur / pompe / catalyseur",
        "dpf_amarillo": "⚠️ Régénération DPF — 30min >1500tr/min",
        "dpf_rojo": "🔴 DPF colmaté — régénération forcée urgente",
        "caja_amarillo": "⚠️ Défaillance boîte / électrovanne / capteur",
        "caja_rojo": "🔴 Défaillance grave boîte",
        "menu": "Sélectionnez un service:",
        "coincidencias": "🔎 {n} résultats:\n\n{liste}\n\nCode complet. Ex: `111 FMI 1`",
        "acceso_admin": "🔑 Accès admin — consultation gratuite",
    },
    "pt": {
        "bienvenida": "🚛 *Bot Diagnóstico IVECO*\n\nSelecione um serviço:",
        "iniciar": "🚀 INICIAR — 5€", "sintomas": "🧠 Sintomas — 10€", "codigo": "🔍 Código erro — 30€",
        "estadisticas": "📊 Estatísticas", "testigo": "Há luz de aviso no painel?",
        "si": "Sim", "no": "Não", "tipo_testigo": "Tipo de aviso:",
        "motor": "Motor", "frenos": "EBS / Freios", "scr": "SCR / AdBlue",
        "dpf": "DPF / Emissões", "caja": "Caixa câmbio",
        "color_testigo": "Cor da luz:", "amarillo": "🟡 Amarelo", "rojo": "🔴 Vermelho",
        "limitado": "Veículo limitado?",
        "pagar_inicio": "🚀 *Consulta INÍCIO — 5€*\n\n1️⃣ Pague aqui:\n{link}\n\n2️⃣ Mesmo *email*\n\n3️⃣ Pressione ✅ *Já paguei*",
        "pagar_sintoma": "🧠 *Consulta SINTOMA — 10€*\n\n1️⃣ Pague aqui:\n{link}\n\n2️⃣ Mesmo *email*\n\n3️⃣ Pressione ✅ *Já paguei*",
        "pagar_codigo": "🔍 *Consulta CÓDIGO — 30€*\n\n1️⃣ Pague aqui:\n{link}\n\n2️⃣ Mesmo *email*\n\n3️⃣ Pressione ✅ *Já paguei*",
        "ya_pagado": "✅ Já paguei", "volver": "🔙 Voltar",
        "pedir_email": "✉️ Introduza o *email* do pagamento:",
        "verificando": "🔄 Verificando...", "pago_ok": "✅ Pagamento verificado. 1 consulta disponível.",
        "continuar": "▶️ Continuar",
        "pago_error": "❌ Pagamento inválido, já usado ou expirado.",
        "reintentar": "🔄 Tentar novamente",
        "intro_codigo": "🔍 Introduza o código:\n_Formato: SPN FMI número (ex: 111 FMI 1)_",
        "intro_sintoma": "🧠 Descreva o sintoma:\n\n_Ex: fumo branco, falta potência..._",
        "codigo_no_encontrado": "❌ Código não encontrado.\n\nFormato: *SPN FMI número*\nEx: `111 FMI 1`",
        "sintoma_no_encontrado": "❌ Sintoma não reconhecido.",
        "sistema": "🏷 Sistema", "pasos": "🔧 *Passos diagnóstico:*",
        "enc_inicio": "📋 3 perguntas para avaliar.", "enc1": "Fácil?", "enc2": "Intuitivo?", "enc3": "Útil?",
        "enc_fin": "✅ Obrigado.\n\nPara nova consulta comece novamente:",
        "motor_amarillo_lim_si": "⚠️ Possível falha SCR (limitado) — IVECO Diagnosis",
        "motor_amarillo_lim_no": "🔧 Oficina — IVECO Diagnosis",
        "motor_rojo": "🔴 FALHA GRAVE → parar e chamar IVECO",
        "frenos_amarillo": "⚠️ Possível falha ABS / EBS",
        "frenos_rojo": "🔴 Falha grave EBS",
        "scr_amarillo": "⚠️ AdBlue baixo / regeneração SCR / NOx",
        "scr_rojo": "🔴 Falha SCR — injetor / bomba / catalisador",
        "dpf_amarillo": "⚠️ Regeneração DPF — 30min >1500rpm",
        "dpf_rojo": "🔴 DPF colmatado — regeneração urgente",
        "caja_amarillo": "⚠️ Falha caixa / eletroválvula / sensor",
        "caja_rojo": "🔴 Falha grave caixa",
        "menu": "Selecione um serviço:",
        "coincidencias": "🔎 {n} resultados:\n\n{lista}\n\nCódigo completo. Ex: `111 FMI 1`",
        "acceso_admin": "🔑 Acesso admin — consulta gratuita",
    },
    "ru": {
        "bienvenida": "🚛 *Бот диагностики IVECO*\n\nВыберите услугу:",
        "iniciar": "🚀 СТАРТ — 5€", "sintomas": "🧠 Симптомы — 10€", "codigo": "🔍 Код ошибки — 30€",
        "estadisticas": "📊 Статистика", "testigo": "Есть предупредительный сигнал?",
        "si": "Да", "no": "Нет", "tipo_testigo": "Тип сигнала:",
        "motor": "Двигатель", "frenos": "EBS / Тормоза", "scr": "SCR / AdBlue",
        "dpf": "DPF / Выбросы", "caja": "КПП",
        "color_testigo": "Цвет сигнала:", "amarillo": "🟡 Жёлтый", "rojo": "🔴 Красный",
        "limitado": "Автомобиль ограничен?",
        "pagar_inicio": "🚀 *Консультация СТАРТ — 5€*\n\n1️⃣ Оплатите здесь:\n{link}\n\n2️⃣ Тот же *email*\n\n3️⃣ Нажмите ✅ *Я оплатил*",
        "pagar_sintoma": "🧠 *Консультация СИМПТОМ — 10€*\n\n1️⃣ Оплатите здесь:\n{link}\n\n2️⃣ Тот же *email*\n\n3️⃣ Нажмите ✅ *Я оплатил*",
        "pagar_codigo": "🔍 *Консультация КОД — 30€*\n\n1️⃣ Оплатите здесь:\n{link}\n\n2️⃣ Тот же *email*\n\n3️⃣ Нажмите ✅ *Я оплатил*",
        "ya_pagado": "✅ Я оплатил", "volver": "🔙 Назад",
        "pedir_email": "✉️ Введите *email* оплаты:",
        "verificando": "🔄 Проверка...", "pago_ok": "✅ Оплата подтверждена. 1 консультация.",
        "continuar": "▶️ Продолжить",
        "pago_error": "❌ Оплата недействительна, уже использована или истекла.",
        "reintentar": "🔄 Повторить",
        "intro_codigo": "🔍 Введите код:\n_Формат: SPN FMI номер (пр: 111 FMI 1)_",
        "intro_sintoma": "🧠 Опишите симптом:\n\n_Пр: белый дым, потеря мощности..._",
        "codigo_no_encontrado": "❌ Код не найден.\n\nФормат: *SPN FMI номер*\nПр: `111 FMI 1`",
        "sintoma_no_encontrado": "❌ Симптом не распознан.",
        "sistema": "🏷 Система", "pasos": "🔧 *Шаги диагностики:*",
        "enc_inicio": "📋 3 вопроса для оценки.", "enc1": "Легко?", "enc2": "Интуитивно?", "enc3": "Помогло?",
        "enc_fin": "✅ Спасибо.\n\nДля новой консультации начните снова:",
        "motor_amarillo_lim_si": "⚠️ Возможная неисправность SCR (ограничен) — IVECO Diagnosis",
        "motor_amarillo_lim_no": "🔧 Мастерская — IVECO Diagnosis",
        "motor_rojo": "🔴 СЕРЬЁЗНАЯ НЕИСПРАВНОСТЬ → остановить и вызвать IVECO",
        "frenos_amarillo": "⚠️ Возможная неисправность ABS / EBS",
        "frenos_rojo": "🔴 Серьёзная неисправность EBS",
        "scr_amarillo": "⚠️ AdBlue низкий / регенерация SCR / NOx",
        "scr_rojo": "🔴 Неисправность SCR — форсунка / насос / катализатор",
        "dpf_amarillo": "⚠️ Регенерация DPF — 30 мин >1500 об/мин",
        "dpf_rojo": "🔴 DPF забит — срочная регенерация",
        "caja_amarillo": "⚠️ Неисправность КПП / соленоид / датчик",
        "caja_rojo": "🔴 Серьёзная неисправность КПП",
        "menu": "Выберите услугу:",
        "coincidencias": "🔎 {n} совпадений:\n\n{lista}\n\nПолный код. Пр: `111 FMI 1`",
        "acceso_admin": "🔑 Доступ администратора — бесплатная консультация",
    },
    "ro": {
        "bienvenida": "🚛 *Bot Diagnostic IVECO*\n\nSelectați un serviciu:",
        "iniciar": "🚀 ÎNCEPUT — 5€", "sintomas": "🧠 Simptome — 10€", "codigo": "🔍 Cod eroare — 30€",
        "estadisticas": "📊 Statistici", "testigo": "Există un martor aprins pe bord?",
        "si": "Da", "no": "Nu", "tipo_testigo": "Tipul martorului:",
        "motor": "Motor", "frenos": "EBS / Frâne", "scr": "SCR / AdBlue",
        "dpf": "DPF / Emisii", "caja": "Cutie viteze",
        "color_testigo": "Culoarea martorului:", "amarillo": "🟡 Galben", "rojo": "🔴 Roșu",
        "limitado": "Vehiculul este limitat?",
        "pagar_inicio": "🚀 *Consultare ÎNCEPUT — 5€*\n\n1️⃣ Plătiți aici:\n{link}\n\n2️⃣ Același *email*\n\n3️⃣ Apăsați ✅ *Am plătit*",
        "pagar_sintoma": "🧠 *Consultare SIMPTOM — 10€*\n\n1️⃣ Plătiți aici:\n{link}\n\n2️⃣ Același *email*\n\n3️⃣ Apăsați ✅ *Am plătit*",
        "pagar_codigo": "🔍 *Consultare COD EROARE — 30€*\n\n1️⃣ Plătiți aici:\n{link}\n\n2️⃣ Același *email*\n\n3️⃣ Apăsați ✅ *Am plătit*",
        "ya_pagado": "✅ Am plătit", "volver": "🔙 Înapoi",
        "pedir_email": "✉️ Introduceți *emailul* folosit la plată:",
        "verificando": "🔄 Verificare...", "pago_ok": "✅ Plată verificată. Aveți 1 consultare disponibilă.",
        "continuar": "▶️ Continuați",
        "pago_error": "❌ Plată invalidă, deja folosită sau expirată.",
        "reintentar": "🔄 Reîncercați",
        "intro_codigo": "🔍 Introduceți codul de eroare:\n_Format: SPN FMI număr (ex: 111 FMI 1)_",
        "intro_sintoma": "🧠 Descrieți simptomul:\n\n_Ex: fum alb, lipsă putere, nu pornește..._",
        "codigo_no_encontrado": "❌ Cod negăsit.\n\nFormat: *SPN FMI număr*\nEx: `111 FMI 1`",
        "sintoma_no_encontrado": "❌ Simptom nerecunoscut.",
        "sistema": "🏷 Sistem", "pasos": "🔧 *Pași diagnostic:*",
        "enc_inicio": "📋 3 întrebări pentru evaluare.", "enc1": "Ușor?", "enc2": "Intuitiv?", "enc3": "Util?",
        "enc_fin": "✅ Mulțumim.\n\nPentru o nouă consultare începeți din nou:",
        "motor_amarillo_lim_si": "⚠️ Posibilă defecțiune SCR (limitat) — IVECO Diagnosis",
        "motor_amarillo_lim_no": "🔧 Service — IVECO Diagnosis",
        "motor_rojo": "🔴 DEFECȚIUNE GRAVĂ → opriți și sunați IVECO",
        "frenos_amarillo": "⚠️ Posibilă defecțiune senzor ABS / EBS",
        "frenos_rojo": "🔴 Defecțiune gravă EBS",
        "scr_amarillo": "⚠️ AdBlue scăzut / regenerare SCR / senzor NOx",
        "scr_rojo": "🔴 Defecțiune SCR — injector / pompă / catalizator",
        "dpf_amarillo": "⚠️ Regenerare DPF necesară — 30min autostradă >1500rpm",
        "dpf_rojo": "🔴 DPF colmatat — regenerare forțată urgentă",
        "caja_amarillo": "⚠️ Defecțiune cutie / electrovalvă / senzor poziție",
        "caja_rojo": "🔴 Defecțiune gravă cutie de viteze",
        "menu": "Selectați un serviciu:",
        "coincidencias": "🔎 {n} rezultate:\n\n{lista}\n\nCod complet. Ex: `111 FMI 1`",
        "acceso_admin": "🔑 Acces administrator — consultare gratuită",
    },
}

def get_lang(update):
    lang = update.effective_user.language_code or "es"
    lang = lang[:2].lower()
    return lang if lang in TEXTOS else "en"

def t(update, key, **kwargs):
    lang = get_lang(update)
    texto = TEXTOS[lang].get(key, TEXTOS["es"].get(key, key))
    if kwargs:
        texto = texto.format(**kwargs)
    return texto

# =====================================================================
# BASE DE DATOS CÓDIGOS IVECO
# =====================================================================
CODIGOS = {
    "111 FMI 1":  {"desc": "Presión aceite motor baja",                "sistema": "Motor",    "diag": ["Verificar nivel aceite", "Sensor presión aceite", "Bomba aceite", "Filtro aceite obstruido"]},
    "111 FMI 18": {"desc": "Presión aceite motor muy baja — parar",    "sistema": "Motor",    "diag": ["Parar motor inmediatamente", "Nivel aceite crítico", "Bomba aceite averiada", "Fuga interna"]},
    "100 FMI 1":  {"desc": "Presión aceite advertencia",               "sistema": "Motor",    "diag": ["Nivel aceite", "Sensor presión", "Circuito lubricación", "Filtro aceite"]},
    "100 FMI 18": {"desc": "Presión aceite crítica",                   "sistema": "Motor",    "diag": ["Parar motor urgente", "Bomba aceite", "Fuga aceite", "Cojinetes"]},
    "110 FMI 0":  {"desc": "Temperatura refrigerante alta",            "sistema": "Motor",    "diag": ["Nivel refrigerante", "Termostato", "Bomba agua", "Radiador obstruido"]},
    "110 FMI 15": {"desc": "Temperatura refrigerante muy alta",        "sistema": "Motor",    "diag": ["Parar motor", "Nivel refrigerante", "Fuga circuito", "Ventilador"]},
    "175 FMI 0":  {"desc": "Temperatura aceite motor alta",            "sistema": "Motor",    "diag": ["Nivel aceite", "Enfriador aceite", "Bomba agua", "Sensor temperatura aceite"]},
    "105 FMI 0":  {"desc": "Temperatura aire admisión alta",           "sistema": "Motor",    "diag": ["Intercooler", "Manguitos intercooler", "Sensor temperatura admisión", "Turbo"]},
    "105 FMI 3":  {"desc": "Sensor temperatura admisión cortocircuito","sistema": "Motor",    "diag": ["Sensor MAT", "Cableado sensor", "Conector oxidado", "ECM"]},
    "102 FMI 1":  {"desc": "Presión boost turbo baja",                 "sistema": "Motor",    "diag": ["Filtro aire obstruido", "Manguitos rotos", "Turbo averiado", "Sensor MAP"]},
    "102 FMI 2":  {"desc": "Sensor presión boost señal errática",      "sistema": "Motor",    "diag": ["Sensor MAP", "Cableado sensor", "Turbo", "Admisión"]},
    "102 FMI 3":  {"desc": "Sensor presión boost cortocircuito",       "sistema": "Motor",    "diag": ["Sensor MAP", "Cableado", "Conector", "ECM"]},
    "102 FMI 4":  {"desc": "Sensor presión boost circuito abierto",    "sistema": "Motor",    "diag": ["Sensor MAP", "Cableado roto", "Conector", "ECM"]},
    "190 FMI 0":  {"desc": "Régimen motor excesivo",                   "sistema": "Motor",    "diag": ["Sensor régimen CKP", "ECM Iveco", "Cableado sensor", "Actuador acelerador"]},
    "190 FMI 2":  {"desc": "Sensor régimen motor señal errática",      "sistema": "Motor",    "diag": ["Sensor CKP sucio", "Corona reluctancia", "Entrehierro sensor", "Cableado"]},
    "190 FMI 8":  {"desc": "Sensor régimen motor señal anormal",       "sistema": "Motor",    "diag": ["Sensor CKP", "Corona reluctancia dañada", "Interferencias", "ECM"]},
    "723 FMI 2":  {"desc": "Sensor árbol levas señal errática",        "sistema": "Motor",    "diag": ["Sensor CMP", "Rueda fónica", "Entrehierro", "Sincronismo distribución"]},
    "723 FMI 8":  {"desc": "Sensor árbol levas sin señal",             "sistema": "Motor",    "diag": ["Sensor CMP", "Cableado", "Rueda fónica", "Distribución"]},
    "157 FMI 1":  {"desc": "Presión rail combustible baja",            "sistema": "Motor",    "diag": ["Filtro combustible", "Bomba alta presión", "Regulador presión rail", "Fugas circuito"]},
    "157 FMI 18": {"desc": "Presión rail combustible muy baja",        "sistema": "Motor",    "diag": ["Bomba alta presión averiada", "Fuga en rail", "Válvula reguladora", "Inyectores"]},
    "157 FMI 0":  {"desc": "Presión rail combustible alta",            "sistema": "Motor",    "diag": ["Válvula limitadora presión", "Regulador presión", "Sensor presión rail", "Inyectores"]},
    "94 FMI 1":   {"desc": "Presión combustible baja alimentación",    "sistema": "Motor",    "diag": ["Filtro combustible obstruido", "Bomba baja presión", "Aire en circuito", "Depósito vacío"]},
    "94 FMI 18":  {"desc": "Presión combustible muy baja",             "sistema": "Motor",    "diag": ["Bomba alimentación averiada", "Filtro colmatado", "Fugas", "Válvula retención"]},
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
    "3563 FMI 1": {"desc": "Presión diferencial DPF alta",             "sistema": "Motor",    "diag": ["Regeneración DPF necesaria", "Filtro DPF obstruido", "Sensor presión diferencial", "Ciclo regeneración"]},
    "3251 FMI 0": {"desc": "Presión diferencial DPF muy alta",         "sistema": "Motor",    "diag": ["DPF colmatado", "Regeneración forzada urgente", "Sustituir DPF", "Sensor presión"]},
    "1173 FMI 0": {"desc": "Temperatura turbo alta",                   "sistema": "Motor",    "diag": ["Carga excesiva", "Refrigeración turbo", "Aceite turbo", "Sensor temperatura turbo"]},
    "3364 FMI 1": {"desc": "Eficiencia SCR baja",                      "sistema": "SCR",      "diag": ["Calidad AdBlue", "Inyector AdBlue", "Sensor NOx aguas abajo", "Catalizador SCR"]},
    "3364 FMI 17":{"desc": "Eficiencia SCR muy baja — limitación",     "sistema": "SCR",      "diag": ["AdBlue contaminado", "Inyector AdBlue obstruido", "Sensor NOx", "Catalizador dañado"]},
    "4334 FMI 7": {"desc": "Dosificación AdBlue incorrecta",           "sistema": "SCR",      "diag": ["Bomba AdBlue", "Inyector AdBlue", "Presión sistema AdBlue", "Líneas obstruidas"]},
    "4334 FMI 14":{"desc": "Inyector AdBlue bloqueado",                "sistema": "SCR",      "diag": ["Limpiar inyector AdBlue", "Cristalización urea", "Sustituir inyector", "Líneas AdBlue"]},
    "1761 FMI 1": {"desc": "Nivel AdBlue bajo",                        "sistema": "SCR",      "diag": ["Rellenar AdBlue", "Sensor nivel AdBlue", "Depósito AdBlue", "Cableado sensor"]},
    "1761 FMI 17":{"desc": "Nivel AdBlue crítico — limitación",        "sistema": "SCR",      "diag": ["Rellenar AdBlue inmediatamente", "Vehículo limitado", "Sensor nivel", "Depósito"]},
    "3516 FMI 3": {"desc": "Sensor NOx aguas arriba cortocircuito",    "sistema": "SCR",      "diag": ["Sensor NOx entrada SCR", "Cableado sensor", "Conector", "SCR ECU"]},
    "3516 FMI 4": {"desc": "Sensor NOx aguas arriba circuito abierto", "sistema": "SCR",      "diag": ["Sensor NOx entrada", "Cableado roto", "Conector", "SCR ECU"]},
    "3490 FMI 3": {"desc": "Sensor NOx aguas abajo cortocircuito",     "sistema": "SCR",      "diag": ["Sensor NOx salida SCR", "Cableado sensor", "Conector", "SCR ECU"]},
    "3490 FMI 4": {"desc": "Sensor NOx aguas abajo circuito abierto",  "sistema": "SCR",      "diag": ["Sensor NOx salida", "Cableado roto", "Conector", "ECU"]},
    "4360 FMI 3": {"desc": "Sensor temperatura SCR cortocircuito",     "sistema": "SCR",      "diag": ["Sensor temperatura SCR", "Cableado", "Conector", "SCR ECU"]},
    "4360 FMI 4": {"desc": "Sensor temperatura SCR circuito abierto",  "sistema": "SCR",      "diag": ["Sensor temperatura SCR", "Cableado roto", "Conector", "ECU"]},
    "5245 FMI 14":{"desc": "Sistema AdBlue congelado",                 "sistema": "SCR",      "diag": ["Calentador depósito AdBlue", "Calentador líneas", "Temperatura ambiente", "Sistema calefacción"]},
    "4076 FMI 1": {"desc": "Presión bomba AdBlue baja",                "sistema": "SCR",      "diag": ["Bomba AdBlue averiada", "Filtro bomba obstruido", "Nivel AdBlue", "Líneas obstruidas"]},
    "84 FMI 2":   {"desc": "Sensor velocidad rueda señal errática",    "sistema": "Frenos",   "diag": ["Sensor ABS rueda", "Corona ABS dañada", "Entrehierro sensor", "Cableado sensor"]},
    "84 FMI 10":  {"desc": "Sensor velocidad rueda señal anormal",     "sistema": "Frenos",   "diag": ["Sensor ABS", "Corona reluctancia sucia", "Cableado", "ECU EBS"]},
    "911 FMI 3":  {"desc": "Sensor presión freno cortocircuito",       "sistema": "Frenos",   "diag": ["Sensor presión circuito freno", "Cableado", "Conector", "ECU EBS"]},
    "911 FMI 4":  {"desc": "Sensor presión freno circuito abierto",    "sistema": "Frenos",   "diag": ["Sensor presión freno", "Cableado roto", "Conector", "ECU EBS"]},
    "597 FMI 3":  {"desc": "Interruptor freno cortocircuito",          "sistema": "Frenos",   "diag": ["Switch freno", "Cableado", "Conector", "ECU EBS"]},
    "597 FMI 4":  {"desc": "Interruptor freno circuito abierto",       "sistema": "Frenos",   "diag": ["Switch freno", "Cableado roto", "Ajuste switch", "ECU EBS"]},
    "1085 FMI 7": {"desc": "Módulo EBS respuesta incorrecta",          "sistema": "Frenos",   "diag": ["ECU EBS", "Alimentación ECU", "CAN bus", "Diagnosis EBS"]},
    "563 FMI 2":  {"desc": "Presión aire circuito freno anormal",      "sistema": "Frenos",   "diag": ["Compresor aire", "Secador aire", "Válvula protección", "Fugas sistema"]},
    "116 FMI 1":  {"desc": "Presión aire depósito baja",               "sistema": "Frenos",   "diag": ["Compresor aire", "Fugas circuito", "Válvula seguridad", "Secador aire"]},
    "116 FMI 17": {"desc": "Presión aire depósito crítica",            "sistema": "Frenos",   "diag": ["Fuga grave", "Compresor averiado", "Válvulas", "Parar vehículo"]},
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
    "5298 FMI 2": {"desc": "Señal radar errática",                     "sistema": "Radar",    "diag": ["Limpieza frontal radar", "Calibración radar", "Golpe parachoques", "Módulo radar"]},
    "5298 FMI 9": {"desc": "Pérdida comunicación módulo radar",        "sistema": "Radar",    "diag": ["CAN bus ADAS", "Alimentación módulo radar", "Cableado", "Módulo radar"]},
    "5298 FMI 14":{"desc": "Radar bloqueado / obstruido",              "sistema": "Radar",    "diag": ["Limpiar rejilla frontal", "Hielo o suciedad", "Daño físico", "Recalibrar"]},
    "639 FMI 9":  {"desc": "Pérdida comunicación CAN bus",             "sistema": "Eléctrico","diag": ["Resistencias terminación CAN 120Ω", "Cableado CAN bus", "Módulos cortocircuito", "Diagnosis"]},
    "639 FMI 14": {"desc": "Error CAN bus general",                    "sistema": "Eléctrico","diag": ["Cortocircuito CAN", "Nodo defectuoso", "Cableado", "Alimentaciones módulos"]},
    "168 FMI 1":  {"desc": "Tensión batería baja",                     "sistema": "Eléctrico","diag": ["Batería descargada", "Alternador", "Consumo parásito", "Bornes batería"]},
    "168 FMI 17": {"desc": "Tensión batería crítica",                  "sistema": "Eléctrico","diag": ["Batería averiada", "Alternador averiado", "Cableado masa", "Bornes oxidados"]},
    "168 FMI 0":  {"desc": "Tensión batería alta",                     "sistema": "Eléctrico","diag": ["Regulador alternador", "Alternador", "Sensor tensión", "Cableado"]},
    "1569 FMI 31":{"desc": "Limitación motor por emisiones OBD",       "sistema": "Eléctrico","diag": ["Sistema SCR defectuoso", "AdBlue nivel crítico", "Fallo NOx reiterado", "Diagnosis completa"]},
    "629 FMI 12": {"desc": "ECM fallo interno",                        "sistema": "Eléctrico","diag": ["Alimentación ECM", "Masa ECM", "Actualizar software Iveco", "Sustituir ECM"]},
    "629 FMI 14": {"desc": "ECM advertencia interna",                  "sistema": "Eléctrico","diag": ["Alimentación ECM", "Temperatura ECM", "Software Iveco", "Diagnosis"]},
    "1031 FMI 7": {"desc": "Actuador embrague respuesta incorrecta",   "sistema": "Embrague", "diag": ["Actuador embrague", "Presión aire actuador", "Desgaste disco embrague", "Calibración"]},
    "1031 FMI 5": {"desc": "Actuador embrague circuito abierto",       "sistema": "Embrague", "diag": ["Cableado actuador", "Conector", "Actuador averiado", "TCU"]},
    "1031 FMI 14":{"desc": "Embrague patinando",                       "sistema": "Embrague", "diag": ["Desgaste disco embrague", "Aceite en embrague", "Calibración", "Actuador"]},
    "1033 FMI 7": {"desc": "Sensor posición embrague incorrecto",      "sistema": "Embrague", "diag": ["Sensor posición embrague", "Cableado sensor", "Calibración sensor", "TCU"]},
}

# =====================================================================
# SÍNTOMAS
# =====================================================================
SINTOMAS = {
    "humo blanco":         "Posible inyector averiado / junta culata / pérdida de compresión",
    "white smoke":         "Possible faulty injector / head gasket / compression loss",
    "fumée blanche":       "Injecteur défaillant / joint culasse / perte compression",
    "fumo branco":         "Injetor avariado / junta cabeça / perda compressão",
    "белый дым":           "Неисправный инжектор / прокладка головки / потеря компрессии",
    "fum alb":             "Injector defect / garnitură chiulasă / pierdere compresie",
    "humo negro":          "Exceso combustible: inyectores / turbo / EGR bloqueado / MAF",
    "black smoke":         "Excess fuel: injectors / turbo / blocked EGR / MAF",
    "fumée noire":         "Excès carburant: injecteurs / turbo / EGR / MAF",
    "fumo preto":          "Excesso combustível: injetores / turbo / EGR / MAF",
    "чёрный дым":          "Избыток топлива: инжекторы / турбо / EGR / MAF",
    "fum negru":           "Exces combustibil: injectoare / turbo / EGR / MAF",
    "humo azul":           "Consumo aceite: sellos válvulas / segmentos / turbo",
    "blue smoke":          "Oil consumption: valve seals / rings / turbo",
    "falta potencia":      "Revisar: turbo / filtro aire / EGR / sistema combustible / sensor MAP",
    "lack of power":       "Check: turbo / air filter / EGR / fuel system / MAP sensor",
    "manque de puissance": "Vérifier: turbo / filtre air / EGR / système carburant / capteur MAP",
    "falta de potência":   "Verificar: turbo / filtro ar / EGR / sistema combustível / sensor MAP",
    "потеря мощности":     "Проверить: турбо / воздушный фильтр / EGR / топливо / MAP",
    "lipsă putere":        "Verificați: turbo / filtru aer / EGR / sistem combustibil / senzor MAP",
    "no arranca":          "Revisar: batería / motor arranque / combustible / sensor CKP / precalentamiento",
    "won't start":         "Check: battery / starter motor / fuel / CKP sensor / glow plugs",
    "ne démarre pas":      "Vérifier: batterie / démarreur / carburant / CKP / préchauffage",
    "não arranca":         "Verificar: bateria / motor arranque / combustível / sensor CKP",
    "не заводится":        "Проверить: аккумулятор / стартер / топливо / CKP / свечи",
    "nu pornește":         "Verificați: baterie / electromotor / combustibil / senzor CKP",
    "tirones":             "Revisar: inyección / sensores MAF-MAP / filtro aire",
    "misfiring":           "Check: injection / MAF-MAP sensors / air filter",
    "consumo alto":        "Revisar: MAF / inyección / turbo / EGR",
    "high consumption":    "Check: MAF / injection / turbo / EGR",
    "fallo adblue":        "Revisar: sistema SCR / inyector AdBlue / bomba / sensor NOx",
    "adblue fault":        "Check: SCR system / AdBlue injector / pump / NOx sensor",
    "défaut adblue":       "Vérifier: SCR / injecteur AdBlue / pompe / NOx",
    "falha adblue":        "Verificar: SCR / injetor AdBlue / bomba / NOx",
    "ошибка adblue":       "Проверить: SCR / форсунка AdBlue / насос / NOx",
    "defect adblue":       "Verificați: sistem SCR / injector AdBlue / pompă / senzor NOx",
    "dpf obstruido":       "Regeneración DPF / sensor presión diferencial / sustituir DPF",
    "dpf blocked":         "DPF regeneration / differential pressure sensor / replace DPF",
    "ruido motor":         "Revisar: nivel aceite / presión aceite / distribución / cojinetes",
    "engine noise":        "Check: oil level / oil pressure / timing / bearings",
    "zgomot motor":        "Verificați: nivel ulei / presiune ulei / distribuție / lagăre",
    "no cambia":           "Revisar: TCU / actuadores caja / presión aire / sensor posición",
    "caliente":            "Revisar: nivel refrigerante / termostato / bomba agua / radiador",
    "overheating":         "Check: coolant level / thermostat / water pump / radiator",
    "frenos duros":        "Revisar: servofreno / presión aire / válvulas EBS / compresor",
    "vibración":           "Revisar: soportes motor / cardán / ruedas / embrague",
}

# =====================================================================
# REGISTRAR ESTADÍSTICAS
# =====================================================================
def registrar_codigo(codigo, sistema):
    codigos = stats.get("codigos_consultados", {})
    codigos[codigo] = codigos.get(codigo, 0) + 1
    stats["codigos_consultados"] = codigos
    sistemas = stats.get("sistemas_consultados", {})
    sistemas[sistema] = sistemas.get(sistema, 0) + 1
    stats["sistemas_consultados"] = sistemas
    stats["codigo_consultas"] = stats.get("codigo_consultas", 0) + 1
    save_json(STATS_FILE, stats)

def registrar_sintoma(sintoma):
    sintomas = stats.get("sintomas_consultados", {})
    sintomas[sintoma] = sintomas.get(sintoma, 0) + 1
    stats["sintomas_consultados"] = sintomas
    stats["sintoma_consultas"] = stats.get("sintoma_consultas", 0) + 1
    save_json(STATS_FILE, stats)

# =====================================================================
# BOTONES
# =====================================================================
def btn_inicio(update, user_id=None):
    es_admin = str(user_id) == str(ADMIN_ID)
    botones = [
        [InlineKeyboardButton(t(update, "iniciar"),  callback_data="pagar_inicio")],
        [InlineKeyboardButton(t(update, "sintomas"), callback_data="pagar_sintoma")],
        [InlineKeyboardButton(t(update, "codigo"),   callback_data="pagar_codigo")],
    ]
    if es_admin:
        botones.append([InlineKeyboardButton(t(update, "estadisticas"), callback_data="stats")])
    return InlineKeyboardMarkup(botones)

def btn_si_no(update, base):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(update, "si"), callback_data=f"{base}_si"),
         InlineKeyboardButton(t(update, "no"), callback_data=f"{base}_no")]
    ])

def btn_tipo(update):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(update, "motor"),  callback_data="motor")],
        [InlineKeyboardButton(t(update, "frenos"), callback_data="frenos")],
        [InlineKeyboardButton(t(update, "scr"),    callback_data="scr")],
        [InlineKeyboardButton(t(update, "dpf"),    callback_data="dpf")],
        [InlineKeyboardButton(t(update, "caja"),   callback_data="caja")],
    ])

def btn_color(update):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(update, "amarillo"), callback_data="amarillo"),
         InlineKeyboardButton(t(update, "rojo"),     callback_data="rojo")]
    ])

def btn_confirmar_pago(update, tipo):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(update, "ya_pagado"), callback_data=f"confirmar_{tipo}")],
        [InlineKeyboardButton(t(update, "volver"),    callback_data="volver")]
    ])

# =====================================================================
# START
# =====================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats["usos"] += 1
    if str(user_id) not in stats["usuarios"]:
        stats["usuarios"].append(str(user_id))
    save_json(STATS_FILE, stats)
    context.user_data.clear()
    await update.effective_message.reply_text("...", reply_markup=ReplyKeyboardRemove())
    await update.effective_message.reply_text(
        t(update, "bienvenida"), parse_mode="Markdown",
        reply_markup=btn_inicio(update, user_id)
    )

# =====================================================================
# ENCUESTA
# =====================================================================
async def lanzar_encuesta(message, update):
    await message.reply_text(t(update, "enc_inicio"))
    await message.reply_text(t(update, "enc1"), reply_markup=btn_si_no(update, "enc1"))

# =====================================================================
# BOTONES
# =====================================================================
async def botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    user_id = update.effective_user.id
    es_admin = str(user_id) == str(ADMIN_ID)

    # ===== PAGOS / ACCESO ADMIN =====
    if d == "pagar_inicio":
        context.user_data.clear()
        if es_admin:
            context.user_data["inicio_libre"] = True
            stats["inicio_consultas"] = stats.get("inicio_consultas", 0) + 1
            save_json(STATS_FILE, stats)
            await q.edit_message_text(
                t(update, "acceso_admin") + "\n\n" + t(update, "testigo"),
                reply_markup=btn_si_no(update, "testigo")
            )
        else:
            await q.edit_message_text(
                t(update, "pagar_inicio", link=LINK_INICIO),
                parse_mode="Markdown", reply_markup=btn_confirmar_pago(update, "inicio")
            )

    elif d == "pagar_sintoma":
        context.user_data.clear()
        if es_admin:
            context.user_data["modo_sintomas"] = True
            stats["sintoma_consultas"] = stats.get("sintoma_consultas", 0) + 1
            save_json(STATS_FILE, stats)
            await q.edit_message_text(
                t(update, "acceso_admin") + "\n\n" + t(update, "intro_sintoma"),
                parse_mode="Markdown"
            )
        else:
            await q.edit_message_text(
                t(update, "pagar_sintoma", link=LINK_SINTOMA),
                parse_mode="Markdown", reply_markup=btn_confirmar_pago(update, "sintoma")
            )

    elif d == "pagar_codigo":
        context.user_data.clear()
        if es_admin:
            context.user_data["modo_codigo"] = True
            stats["codigo_consultas"] = stats.get("codigo_consultas", 0) + 1
            save_json(STATS_FILE, stats)
            await q.edit_message_text(
                t(update, "acceso_admin") + "\n\n" + t(update, "intro_codigo"),
                parse_mode="Markdown"
            )
        else:
            await q.edit_message_text(
                t(update, "pagar_codigo", link=LINK_CODIGO),
                parse_mode="Markdown", reply_markup=btn_confirmar_pago(update, "codigo")
            )

    elif d.startswith("confirmar_"):
        tipo = d.split("_")[1]
        context.user_data["esperando_email"] = tipo
        await q.edit_message_text(t(update, "pedir_email"), parse_mode="Markdown")

    # ===== FLUJO INICIO =====
    elif d == "inicio_verificado" or d == "testigo_check":
        await q.edit_message_text(t(update, "testigo"), reply_markup=btn_si_no(update, "testigo"))

    elif d == "testigo_si":
        await q.edit_message_text(t(update, "tipo_testigo"), reply_markup=btn_tipo(update))

    elif d == "testigo_no":
        context.user_data["modo_sintomas"] = True
        await q.edit_message_text(t(update, "intro_sintoma"), parse_mode="Markdown")

    elif d in ["motor", "frenos", "scr", "dpf", "caja"]:
        context.user_data["tipo"] = d
        await q.edit_message_text(t(update, "color_testigo"), reply_markup=btn_color(update))

    elif d == "amarillo" and context.user_data.get("tipo") == "motor":
        await q.edit_message_text(t(update, "limitado"), reply_markup=btn_si_no(update, "lim"))

    elif d == "lim_si":
        stats["inicio_consultas"] = stats.get("inicio_consultas", 0) + 1
        save_json(STATS_FILE, stats)
        await q.edit_message_text(t(update, "motor_amarillo_lim_si"))
        await lanzar_encuesta(q.message, update)

    elif d == "lim_no":
        await q.edit_message_text(t(update, "motor_amarillo_lim_no"))
        await lanzar_encuesta(q.message, update)

    elif d == "rojo" and context.user_data.get("tipo") == "motor":
        await q.edit_message_text(t(update, "motor_rojo"))
        await lanzar_encuesta(q.message, update)

    elif d == "amarillo" and context.user_data.get("tipo") == "frenos":
        await q.edit_message_text(t(update, "frenos_amarillo"))
        await lanzar_encuesta(q.message, update)

    elif d == "rojo" and context.user_data.get("tipo") == "frenos":
        await q.edit_message_text(t(update, "frenos_rojo"))
        await lanzar_encuesta(q.message, update)

    elif d == "amarillo" and context.user_data.get("tipo") == "scr":
        await q.edit_message_text(t(update, "scr_amarillo"))
        await lanzar_encuesta(q.message, update)

    elif d == "rojo" and context.user_data.get("tipo") == "scr":
        await q.edit_message_text(t(update, "scr_rojo"))
        await lanzar_encuesta(q.message, update)

    elif d == "amarillo" and context.user_data.get("tipo") == "dpf":
        await q.edit_message_text(t(update, "dpf_amarillo"))
        await lanzar_encuesta(q.message, update)

    elif d == "rojo" and context.user_data.get("tipo") == "dpf":
        await q.edit_message_text(t(update, "dpf_rojo"))
        await lanzar_encuesta(q.message, update)

    elif d == "amarillo" and context.user_data.get("tipo") == "caja":
        await q.edit_message_text(t(update, "caja_amarillo"))
        await lanzar_encuesta(q.message, update)

    elif d == "rojo" and context.user_data.get("tipo") == "caja":
        await q.edit_message_text(t(update, "caja_rojo"))
        await lanzar_encuesta(q.message, update)

    # ===== ESTADÍSTICAS =====
    elif d == "stats":
        if not es_admin:
            await q.answer("⛔ No autorizado", show_alert=True)
            return
        codigos_dict  = stats.get("codigos_consultados", {})
        sintomas_dict = stats.get("sintomas_consultados", {})
        sistemas_dict = stats.get("sistemas_consultados", {})
        top_cod = sorted(codigos_dict.items(),  key=lambda x: x[1], reverse=True)[:5]
        top_sin = sorted(sintomas_dict.items(), key=lambda x: x[1], reverse=True)[:5]
        top_sis = sorted(sistemas_dict.items(), key=lambda x: x[1], reverse=True)[:5]
        top_cod_txt = "\n".join([f"  • {c} → {n}x" for c, n in top_cod]) or "  Sin datos"
        top_sin_txt = "\n".join([f"  • {s} → {n}x" for s, n in top_sin]) or "  Sin datos"
        top_sis_txt = "\n".join([f"  • {s} → {n}x" for s, n in top_sis]) or "  Sin datos"
        ingresos = (stats.get("ingresos_inicio", 0) * 5 +
                    stats.get("ingresos_sintoma", 0) * 10 +
                    stats.get("ingresos_codigo", 0) * 30)
        txt = (
            f"📊 *Estadísticas IVECO*\n\n"
            f"👥 Usuarios únicos: {len(stats['usuarios'])}\n"
            f"🔢 Usos totales: {stats['usos']}\n\n"
            f"📋 *Consultas por tipo:*\n"
            f"  🚀 Inicio: {stats.get('inicio_consultas', 0)}\n"
            f"  🧠 Síntomas: {stats.get('sintoma_consultas', 0)}\n"
            f"  🔍 Códigos: {stats.get('codigo_consultas', 0)}\n\n"
            f"💶 *Ingresos estimados: {ingresos}€*\n"
            f"  Inicio: {stats.get('ingresos_inicio', 0)} pagos\n"
            f"  Síntoma: {stats.get('ingresos_sintoma', 0)} pagos\n"
            f"  Código: {stats.get('ingresos_codigo', 0)} pagos\n\n"
            f"🔥 *Top 5 códigos:*\n{top_cod_txt}\n\n"
            f"🧠 *Top 5 síntomas:*\n{top_sin_txt}\n\n"
            f"🏷 *Sistemas más consultados:*\n{top_sis_txt}\n\n"
            f"📋 *Encuestas:*\n"
            f"  ✅ Fácil: {stats.get('facil_si', 0)}  ❌ {stats.get('facil_no', 0)}\n"
            f"  ✅ Intuitivo: {stats.get('intuitivo_si', 0)}  ❌ {stats.get('intuitivo_no', 0)}\n"
            f"  ✅ Útil: {stats.get('util_si', 0)}  ❌ {stats.get('util_no', 0)}"
        )
        await q.edit_message_text(txt, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(update, "volver"), callback_data="volver")]]))

    elif d == "volver":
        context.user_data.clear()
        await q.edit_message_text(t(update, "menu"), reply_markup=btn_inicio(update, user_id))

    elif d.startswith("enc1"):
        k = "facil_si" if "si" in d else "facil_no"
        stats[k] = stats.get(k, 0) + 1
        save_json(STATS_FILE, stats)
        await q.edit_message_text(t(update, "enc2"), reply_markup=btn_si_no(update, "enc2"))

    elif d.startswith("enc2"):
        k = "intuitivo_si" if "si" in d else "intuitivo_no"
        stats[k] = stats.get(k, 0) + 1
        save_json(STATS_FILE, stats)
        await q.edit_message_text(t(update, "enc3"), reply_markup=btn_si_no(update, "enc3"))

    elif d.startswith("enc3"):
        k = "util_si" if "si" in d else "util_no"
        stats[k] = stats.get(k, 0) + 1
        save_json(STATS_FILE, stats)
        await q.edit_message_text(t(update, "enc_fin"), reply_markup=btn_inicio(update, user_id))

# =====================================================================
# TEXTO
# =====================================================================
async def texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto_user = update.message.text.strip()

    # ===== VERIFICACIÓN EMAIL =====
    if context.user_data.get("esperando_email"):
        tipo = context.user_data.pop("esperando_email")
        email = texto_user.strip().lower()
        await update.message.reply_text(t(update, "verificando"))
        pagado = verificar_pago(email, tipo)

        if pagado:
            if tipo == "inicio":
                stats["ingresos_inicio"] = stats.get("ingresos_inicio", 0) + 1
                stats["inicio_consultas"] = stats.get("inicio_consultas", 0) + 1
                save_json(STATS_FILE, stats)
                await update.message.reply_text(
                    t(update, "pago_ok"),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(t(update, "continuar"), callback_data="testigo_check")]
                    ])
                )
            elif tipo == "sintoma":
                stats["ingresos_sintoma"] = stats.get("ingresos_sintoma", 0) + 1
                stats["sintoma_consultas"] = stats.get("sintoma_consultas", 0) + 1
                save_json(STATS_FILE, stats)
                context.user_data["modo_sintomas"] = True
                await update.message.reply_text(
                    t(update, "pago_ok") + "\n\n" + t(update, "intro_sintoma"),
                    parse_mode="Markdown"
                )
            elif tipo == "codigo":
                stats["ingresos_codigo"] = stats.get("ingresos_codigo", 0) + 1
                stats["codigo_consultas"] = stats.get("codigo_consultas", 0) + 1
                save_json(STATS_FILE, stats)
                context.user_data["modo_codigo"] = True
                await update.message.reply_text(
                    t(update, "pago_ok") + "\n\n" + t(update, "intro_codigo"),
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(
                t(update, "pago_error"),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t(update, "reintentar"), callback_data=f"confirmar_{tipo}")],
                    [InlineKeyboardButton(t(update, "volver"),    callback_data="volver")]
                ])
            )
        return

    # ===== MODO CÓDIGO =====
    if context.user_data.get("modo_codigo"):
        busqueda = texto_user.upper().strip()
        if busqueda in CODIGOS:
            resultados = [(busqueda, CODIGOS[busqueda])]
        else:
            resultados = [(k, v) for k, v in CODIGOS.items() if busqueda in k]

        if not resultados:
            await update.message.reply_text(t(update, "codigo_no_encontrado"), parse_mode="Markdown")
            return

        if len(resultados) == 1:
            context.user_data["modo_codigo"] = False
            clave, data = resultados[0]
            registrar_codigo(clave, data["sistema"])
            diag = "\n".join([f"  • {x}" for x in data["diag"]])
            msg = (
                f"🔍 *{clave}*\n"
                f"{t(update, 'sistema')}: {data['sistema']}\n"
                f"📋 {data['desc']}\n\n"
                f"{t(update, 'pasos')}\n{diag}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
            await lanzar_encuesta(update.message, update)
        else:
            lista = "\n".join([f"• *{k}* — {v['desc']}" for k, v in resultados[:8]])
            await update.message.reply_text(
                t(update, "coincidencias", n=len(resultados), lista=lista),
                parse_mode="Markdown"
            )
        return

    # ===== MODO SÍNTOMAS =====
    if context.user_data.get("modo_sintomas"):
        context.user_data["modo_sintomas"] = False
        texto_lower = texto_user.lower()
        encontrado = False
        for s, resp in SINTOMAS.items():
            if s in texto_lower:
                registrar_sintoma(s)
                await update.message.reply_text(
                    f"🧠 *{s.capitalize()}*\n\n🔧 {resp}", parse_mode="Markdown"
                )
                encontrado = True
                break
        if not encontrado:
            await update.message.reply_text(t(update, "sintoma_no_encontrado"), parse_mode="Markdown")
        await lanzar_encuesta(update.message, update)
        return

    await update.message.reply_text(t(update, "menu"), reply_markup=btn_inicio(update, user_id))

# =====================================================================
# APP — webhook Telegram
# =====================================================================
import asyncio

async def post_init(application):
    global _application, _loop
    _application = application
    _loop = asyncio.get_event_loop()
    webhook_url = f"{RENDER_URL}/{TOKEN}"
    await application.bot.set_webhook(url=webhook_url)
    print(f"✅ Webhook Telegram configurado: {webhook_url}")

app = (
    ApplicationBuilder()
    .token(TOKEN)
    .post_init(post_init)
    .build()
)

_application = app

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(botones))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto))

print("✅ Bot IVECO — Webhook + 6 idiomas + Admin libre + Estadísticas OK 🚛")
app.run_polling(drop_pending_updates=True)
