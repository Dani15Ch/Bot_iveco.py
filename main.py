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
# KEEP-ALIVE
# =====================================================================
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot IVECO activo")
    def log_message(self, format, *args):
        pass

def iniciar_servidor():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), KeepAlive)
    server.serve_forever()

threading.Thread(target=iniciar_servidor, daemon=True).start()

# =====================================================================
# TRADUCCIONES
# =====================================================================
TEXTOS = {
    "es": {
        "bienvenida": "🚛 *Bot Diagnóstico IVECO*\n\nSelecciona el servicio:",
        "iniciar": "🚀 INICIAR — 5€",
        "sintomas": "🧠 Síntomas — 10€",
        "codigo": "🔍 Código error — 30€",
        "estadisticas": "📊 Estadísticas",
        "testigo": "¿Testigo encendido en el cuadro?",
        "si": "Sí",
        "no": "No",
        "tipo_testigo": "Tipo de testigo:",
        "motor": "Motor",
        "frenos": "EBS / Frenos",
        "scr": "SCR",
        "radar": "Radar",
        "caja": "Caja cambios",
        "color_testigo": "Color del testigo:",
        "amarillo": "🟡 Amarillo",
        "rojo": "🔴 Rojo",
        "limitado": "¿Vehículo limitado?",
        "pagar_inicio": "🚀 *Consulta INICIO — 5€*\n\n1️⃣ Realiza el pago aquí:\n{link}\n\n2️⃣ Usa el *mismo email* con el que pagas\n\n3️⃣ Pulsa ✅ *Ya he pagado*",
        "pagar_sintoma": "🧠 *Consulta SÍNTOMA — 10€*\n\n1️⃣ Realiza el pago aquí:\n{link}\n\n2️⃣ Usa el *mismo email* con el que pagas\n\n3️⃣ Pulsa ✅ *Ya he pagado*",
        "pagar_codigo": "🔍 *Consulta CÓDIGO ERROR — 30€*\n\n1️⃣ Realiza el pago aquí:\n{link}\n\n2️⃣ Usa el *mismo email* con el que pagas\n\n3️⃣ Pulsa ✅ *Ya he pagado*",
        "ya_pagado": "✅ Ya he pagado",
        "volver": "🔙 Volver",
        "pedir_email": "✉️ Introduce el *email* con el que realizaste el pago:",
        "verificando": "🔄 Verificando pago...",
        "pago_ok": "✅ Pago verificado. Tienes 1 consulta disponible.",
        "continuar": "▶️ Continuar",
        "pago_error": "❌ No se encontró el pago con ese email.\n\nComprueba que:\n• El email es correcto\n• El pago está completado\n• Espera unos segundos y reintenta",
        "reintentar": "🔄 Reintentar",
        "intro_codigo": "🔍 Introduce el código de error:\n_Formato: SPN FMI número (ej: 111 FMI 1)_",
        "intro_sintoma": "🧠 Describe el síntoma del vehículo:\n\n_Ej: humo blanco, falta potencia, no arranca, tirones..._",
        "codigo_no_encontrado": "❌ Código no encontrado.\n\nFormato correcto: *SPN FMI número*\nEjemplo: `111 FMI 1`\n\nVuelve a introducir el código:",
        "sintoma_no_encontrado": "❌ Síntoma no reconocido.\n\nPrueba con: _humo blanco, humo negro, falta potencia, no arranca, tirones, consumo alto, fallo adblue..._",
        "sistema": "🏷 Sistema",
        "pasos": "🔧 *Pasos diagnóstico:*",
        "enc_inicio": "📋 3 preguntas rápidas para valorar el bot.",
        "enc1": "¿Le ha resultado fácil?",
        "enc2": "¿Le ha parecido intuitivo?",
        "enc3": "¿Le ha ayudado?",
        "enc_fin": "✅ Gracias por su valoración.\n\nPara una nueva consulta vuelve a empezar:",
        "scr_amarillo": "⚠️ Posible regeneración en curso",
        "scr_rojo": "🔴 Fallo sistema SCR / módulo AdBlue bloqueado / fallo inyector / fuga AdBlue",
        "motor_amarillo_lim_si": "⚠️ Posible fallo sistema SCR (vehículo limitado)",
        "motor_amarillo_lim_no": "🔧 Revisar en taller",
        "motor_rojo": "🔴 FALLO GRAVE → taller urgente",
        "frenos_amarillo": "⚠️ Posible fallo sensores EBS / sensores velocidad ruedas",
        "frenos_rojo": "🔴 Pérdida de aire / fallo eléctrico",
        "radar_amarillo": "⚠️ Fallo calibración / radar desalineado / radar golpeado",
        "radar_rojo": "🔴 Defecto radar / fallo eléctrico",
        "caja_amarillo": "⚠️ Fallo eléctrico / fallo electroválvulas",
        "caja_rojo": "🔴 Fuga de aire / bloqueo centralita",
        "menu": "Selecciona el servicio:",
        "coincidencias": "🔎 {n} coincidencias encontradas:\n\n{lista}\n\nIntroduce el código *completo*. Ejemplo: `111 FMI 1`",
    },
    "en": {
        "bienvenida": "🚛 *IVECO Diagnostic Bot*\n\nSelect a service:",
        "iniciar": "🚀 START — 5€",
        "sintomas": "🧠 Symptoms — 10€",
        "codigo": "🔍 Error code — 30€",
        "estadisticas": "📊 Statistics",
        "testigo": "Is there a warning light on the dashboard?",
        "si": "Yes",
        "no": "No",
        "tipo_testigo": "Type of warning light:",
        "motor": "Engine",
        "frenos": "EBS / Brakes",
        "scr": "SCR",
        "radar": "Radar",
        "caja": "Gearbox",
        "color_testigo": "Warning light color:",
        "amarillo": "🟡 Yellow",
        "rojo": "🔴 Red",
        "limitado": "Is the vehicle limited?",
        "pagar_inicio": "🚀 *START Consultation — 5€*\n\n1️⃣ Make the payment here:\n{link}\n\n2️⃣ Use the *same email* you pay with\n\n3️⃣ Press ✅ *I have paid*",
        "pagar_sintoma": "🧠 *SYMPTOM Consultation — 10€*\n\n1️⃣ Make the payment here:\n{link}\n\n2️⃣ Use the *same email* you pay with\n\n3️⃣ Press ✅ *I have paid*",
        "pagar_codigo": "🔍 *ERROR CODE Consultation — 30€*\n\n1️⃣ Make the payment here:\n{link}\n\n2️⃣ Use the *same email* you pay with\n\n3️⃣ Press ✅ *I have paid*",
        "ya_pagado": "✅ I have paid",
        "volver": "🔙 Back",
        "pedir_email": "✉️ Enter the *email* you used for the payment:",
        "verificando": "🔄 Verifying payment...",
        "pago_ok": "✅ Payment verified. You have 1 consultation available.",
        "continuar": "▶️ Continue",
        "pago_error": "❌ Payment not found with that email.\n\nCheck that:\n• The email is correct\n• The payment is completed\n• Wait a few seconds and try again",
        "reintentar": "🔄 Retry",
        "intro_codigo": "🔍 Enter the error code:\n_Format: SPN FMI number (e.g: 111 FMI 1)_",
        "intro_sintoma": "🧠 Describe the vehicle symptom:\n\n_E.g: white smoke, lack of power, won't start, misfiring..._",
        "codigo_no_encontrado": "❌ Code not found.\n\nCorrect format: *SPN FMI number*\nExample: `111 FMI 1`\n\nEnter the code again:",
        "sintoma_no_encontrado": "❌ Symptom not recognized.\n\nTry: _white smoke, black smoke, lack of power, won't start, misfiring, high consumption, adblue fault..._",
        "sistema": "🏷 System",
        "pasos": "🔧 *Diagnostic steps:*",
        "enc_inicio": "📋 3 quick questions to rate the bot.",
        "enc1": "Was it easy to use?",
        "enc2": "Was it intuitive?",
        "enc3": "Did it help you?",
        "enc_fin": "✅ Thank you for your feedback.\n\nFor a new consultation start again:",
        "scr_amarillo": "⚠️ Possible ongoing regeneration",
        "scr_rojo": "🔴 SCR system failure / AdBlue module blocked / injector fault / AdBlue leak",
        "motor_amarillo_lim_si": "⚠️ Possible SCR system fault (vehicle limited)",
        "motor_amarillo_lim_no": "🔧 Check at workshop",
        "motor_rojo": "🔴 SERIOUS FAULT → urgent workshop",
        "frenos_amarillo": "⚠️ Possible EBS sensor fault / wheel speed sensors",
        "frenos_rojo": "🔴 Air loss / electrical fault",
        "radar_amarillo": "⚠️ Calibration fault / misaligned radar / damaged radar",
        "radar_rojo": "🔴 Radar defect / electrical fault",
        "caja_amarillo": "⚠️ Electrical fault / solenoid valve fault",
        "caja_rojo": "🔴 Air leak / ECU lockout",
        "menu": "Select a service:",
        "coincidencias": "🔎 {n} matches found:\n\n{lista}\n\nEnter the *full* code. Example: `111 FMI 1`",
    },
    "fr": {
        "bienvenida": "🚛 *Bot Diagnostic IVECO*\n\nSélectionnez un service:",
        "iniciar": "🚀 DÉMARRER — 5€",
        "sintomas": "🧠 Symptômes — 10€",
        "codigo": "🔍 Code erreur — 30€",
        "estadisticas": "📊 Statistiques",
        "testigo": "Y a-t-il un voyant allumé au tableau de bord?",
        "si": "Oui",
        "no": "Non",
        "tipo_testigo": "Type de voyant:",
        "motor": "Moteur",
        "frenos": "EBS / Freins",
        "scr": "SCR",
        "radar": "Radar",
        "caja": "Boîte de vitesses",
        "color_testigo": "Couleur du voyant:",
        "amarillo": "🟡 Jaune",
        "rojo": "🔴 Rouge",
        "limitado": "Le véhicule est-il limité?",
        "pagar_inicio": "🚀 *Consultation DÉMARRAGE — 5€*\n\n1️⃣ Effectuez le paiement ici:\n{link}\n\n2️⃣ Utilisez le *même email* que pour le paiement\n\n3️⃣ Appuyez sur ✅ *J'ai payé*",
        "pagar_sintoma": "🧠 *Consultation SYMPTÔME — 10€*\n\n1️⃣ Effectuez le paiement ici:\n{link}\n\n2️⃣ Utilisez le *même email* que pour le paiement\n\n3️⃣ Appuyez sur ✅ *J'ai payé*",
        "pagar_codigo": "🔍 *Consultation CODE ERREUR — 30€*\n\n1️⃣ Effectuez le paiement ici:\n{link}\n\n2️⃣ Utilisez le *même email* que pour le paiement\n\n3️⃣ Appuyez sur ✅ *J'ai payé*",
        "ya_pagado": "✅ J'ai payé",
        "volver": "🔙 Retour",
        "pedir_email": "✉️ Entrez l'*email* utilisé pour le paiement:",
        "verificando": "🔄 Vérification du paiement...",
        "pago_ok": "✅ Paiement vérifié. Vous avez 1 consultation disponible.",
        "continuar": "▶️ Continuer",
        "pago_error": "❌ Paiement non trouvé avec cet email.\n\nVérifiez que:\n• L'email est correct\n• Le paiement est complété\n• Attendez quelques secondes et réessayez",
        "reintentar": "🔄 Réessayer",
        "intro_codigo": "🔍 Entrez le code d'erreur:\n_Format: SPN FMI numéro (ex: 111 FMI 1)_",
        "intro_sintoma": "🧠 Décrivez le symptôme du véhicule:\n\n_Ex: fumée blanche, manque de puissance, ne démarre pas..._",
        "codigo_no_encontrado": "❌ Code non trouvé.\n\nFormat correct: *SPN FMI numéro*\nExemple: `111 FMI 1`\n\nEntrez à nouveau le code:",
        "sintoma_no_encontrado": "❌ Symptôme non reconnu.\n\nEssayez: _fumée blanche, fumée noire, manque de puissance, ne démarre pas..._",
        "sistema": "🏷 Système",
        "pasos": "🔧 *Étapes de diagnostic:*",
        "enc_inicio": "📋 3 questions rapides pour évaluer le bot.",
        "enc1": "Était-ce facile à utiliser?",
        "enc2": "Était-ce intuitif?",
        "enc3": "Cela vous a-t-il aidé?",
        "enc_fin": "✅ Merci pour votre évaluation.\n\nPour une nouvelle consultation recommencez:",
        "scr_amarillo": "⚠️ Possible régénération en cours",
        "scr_rojo": "🔴 Défaillance système SCR / module AdBlue bloqué / injecteur / fuite AdBlue",
        "motor_amarillo_lim_si": "⚠️ Possible défaillance système SCR (véhicule limité)",
        "motor_amarillo_lim_no": "🔧 Vérifier en atelier",
        "motor_rojo": "🔴 DÉFAILLANCE GRAVE → atelier urgent",
        "frenos_amarillo": "⚠️ Possible défaillance capteurs EBS / capteurs vitesse roues",
        "frenos_rojo": "🔴 Perte d'air / défaillance électrique",
        "radar_amarillo": "⚠️ Défaut calibration / radar désaligné / radar endommagé",
        "radar_rojo": "🔴 Défaut radar / défaillance électrique",
        "caja_amarillo": "⚠️ Défaillance électrique / électrovanne",
        "caja_rojo": "🔴 Fuite d'air / blocage calculateur",
        "menu": "Sélectionnez un service:",
        "coincidencias": "🔎 {n} correspondances trouvées:\n\n{liste}\n\nEntrez le code *complet*. Exemple: `111 FMI 1`",
    },
    "pt": {
        "bienvenida": "🚛 *Bot Diagnóstico IVECO*\n\nSelecione um serviço:",
        "iniciar": "🚀 INICIAR — 5€",
        "sintomas": "🧠 Sintomas — 10€",
        "codigo": "🔍 Código de erro — 30€",
        "estadisticas": "📊 Estatísticas",
        "testigo": "Há alguma luz de aviso no painel?",
        "si": "Sim",
        "no": "Não",
        "tipo_testigo": "Tipo de aviso:",
        "motor": "Motor",
        "frenos": "EBS / Freios",
        "scr": "SCR",
        "radar": "Radar",
        "caja": "Caixa de câmbio",
        "color_testigo": "Cor da luz de aviso:",
        "amarillo": "🟡 Amarelo",
        "rojo": "🔴 Vermelho",
        "limitado": "O veículo está limitado?",
        "pagar_inicio": "🚀 *Consulta INÍCIO — 5€*\n\n1️⃣ Faça o pagamento aqui:\n{link}\n\n2️⃣ Use o *mesmo email* do pagamento\n\n3️⃣ Pressione ✅ *Já paguei*",
        "pagar_sintoma": "🧠 *Consulta SINTOMA — 10€*\n\n1️⃣ Faça o pagamento aqui:\n{link}\n\n2️⃣ Use o *mesmo email* do pagamento\n\n3️⃣ Pressione ✅ *Já paguei*",
        "pagar_codigo": "🔍 *Consulta CÓDIGO ERRO — 30€*\n\n1️⃣ Faça o pagamento aqui:\n{link}\n\n2️⃣ Use o *mesmo email* do pagamento\n\n3️⃣ Pressione ✅ *Já paguei*",
        "ya_pagado": "✅ Já paguei",
        "volver": "🔙 Voltar",
        "pedir_email": "✉️ Introduza o *email* utilizado no pagamento:",
        "verificando": "🔄 Verificando pagamento...",
        "pago_ok": "✅ Pagamento verificado. Tem 1 consulta disponível.",
        "continuar": "▶️ Continuar",
        "pago_error": "❌ Pagamento não encontrado com esse email.\n\nVerifique que:\n• O email está correto\n• O pagamento foi concluído\n• Aguarde alguns segundos e tente novamente",
        "reintentar": "🔄 Tentar novamente",
        "intro_codigo": "🔍 Introduza o código de erro:\n_Formato: SPN FMI número (ex: 111 FMI 1)_",
        "intro_sintoma": "🧠 Descreva o sintoma do veículo:\n\n_Ex: fumo branco, falta de potência, não arranca, solavancos..._",
        "codigo_no_encontrado": "❌ Código não encontrado.\n\nFormato correto: *SPN FMI número*\nExemplo: `111 FMI 1`\n\nIntroduza o código novamente:",
        "sintoma_no_encontrado": "❌ Sintoma não reconhecido.\n\nTente: _fumo branco, fumo preto, falta de potência, não arranca..._",
        "sistema": "🏷 Sistema",
        "pasos": "🔧 *Passos de diagnóstico:*",
        "enc_inicio": "📋 3 perguntas rápidas para avaliar o bot.",
        "enc1": "Foi fácil de usar?",
        "enc2": "Foi intuitivo?",
        "enc3": "Ajudou-o?",
        "enc_fin": "✅ Obrigado pela sua avaliação.\n\nPara uma nova consulta comece novamente:",
        "scr_amarillo": "⚠️ Possível regeneração em curso",
        "scr_rojo": "🔴 Falha sistema SCR / módulo AdBlue bloqueado / injetor / fuga AdBlue",
        "motor_amarillo_lim_si": "⚠️ Possível falha sistema SCR (veículo limitado)",
        "motor_amarillo_lim_no": "🔧 Verificar na oficina",
        "motor_rojo": "🔴 FALHA GRAVE → oficina urgente",
        "frenos_amarillo": "⚠️ Possível falha sensores EBS / sensores velocidade rodas",
        "frenos_rojo": "🔴 Perda de ar / falha elétrica",
        "radar_amarillo": "⚠️ Falha calibração / radar desalinhado / radar danificado",
        "radar_rojo": "🔴 Defeito radar / falha elétrica",
        "caja_amarillo": "⚠️ Falha elétrica / eletroválvula",
        "caja_rojo": "🔴 Fuga de ar / bloqueio centralita",
        "menu": "Selecione um serviço:",
        "coincidencias": "🔎 {n} correspondências encontradas:\n\n{lista}\n\nIntroduza o código *completo*. Exemplo: `111 FMI 1`",
    },
    "ru": {
        "bienvenida": "🚛 *Бот диагностики IVECO*\n\nВыберите услугу:",
        "iniciar": "🚀 СТАРТ — 5€",
        "sintomas": "🧠 Симптомы — 10€",
        "codigo": "🔍 Код ошибки — 30€",
        "estadisticas": "📊 Статистика",
        "testigo": "Есть ли предупредительный сигнал на панели?",
        "si": "Да",
        "no": "Нет",
        "tipo_testigo": "Тип сигнала:",
        "motor": "Двигатель",
        "frenos": "EBS / Тормоза",
        "scr": "SCR",
        "radar": "Радар",
        "caja": "Коробка передач",
        "color_testigo": "Цвет сигнала:",
        "amarillo": "🟡 Жёлтый",
        "rojo": "🔴 Красный",
        "limitado": "Автомобиль ограничен?",
        "pagar_inicio": "🚀 *Консультация СТАРТ — 5€*\n\n1️⃣ Оплатите здесь:\n{link}\n\n2️⃣ Используйте *тот же email* что при оплате\n\n3️⃣ Нажмите ✅ *Я оплатил*",
        "pagar_sintoma": "🧠 *Консультация СИМПТОМ — 10€*\n\n1️⃣ Оплатите здесь:\n{link}\n\n2️⃣ Используйте *тот же email* что при оплате\n\n3️⃣ Нажмите ✅ *Я оплатил*",
        "pagar_codigo": "🔍 *Консультация КОД ОШИБКИ — 30€*\n\n1️⃣ Оплатите здесь:\n{link}\n\n2️⃣ Используйте *тот же email* что при оплате\n\n3️⃣ Нажмите ✅ *Я оплатил*",
        "ya_pagado": "✅ Я оплатил",
        "volver": "🔙 Назад",
        "pedir_email": "✉️ Введите *email* использованный при оплате:",
        "verificando": "🔄 Проверка оплаты...",
        "pago_ok": "✅ Оплата подтверждена. У вас 1 консультация.",
        "continuar": "▶️ Продолжить",
        "pago_error": "❌ Оплата не найдена с этим email.\n\nПроверьте:\n• Email верный\n• Оплата завершена\n• Подождите и попробуйте снова",
        "reintentar": "🔄 Повторить",
        "intro_codigo": "🔍 Введите код ошибки:\n_Формат: SPN FMI номер (пр: 111 FMI 1)_",
        "intro_sintoma": "🧠 Опишите симптом автомобиля:\n\n_Пр: белый дым, потеря мощности, не заводится..._",
        "codigo_no_encontrado": "❌ Код не найден.\n\nПравильный формат: *SPN FMI номер*\nПример: `111 FMI 1`\n\nВведите код снова:",
        "sintoma_no_encontrado": "❌ Симптом не распознан.\n\nПопробуйте: _белый дым, чёрный дым, потеря мощности, не заводится..._",
        "sistema": "🏷 Система",
        "pasos": "🔧 *Шаги диагностики:*",
        "enc_inicio": "📋 3 быстрых вопроса для оценки бота.",
        "enc1": "Было ли легко использовать?",
        "enc2": "Было ли интуитивно понятно?",
        "enc3": "Помогло ли вам?",
        "enc_fin": "✅ Спасибо за оценку.\n\nДля новой консультации начните снова:",
        "scr_amarillo": "⚠️ Возможная регенерация в процессе",
        "scr_rojo": "🔴 Неисправность SCR / заблокирован модуль AdBlue / инжектор / утечка AdBlue",
        "motor_amarillo_lim_si": "⚠️ Возможная неисправность SCR (автомобиль ограничен)",
        "motor_amarillo_lim_no": "🔧 Проверить в мастерской",
        "motor_rojo": "🔴 СЕРЬЁЗНАЯ НЕИСПРАВНОСТЬ → срочно в мастерскую",
        "frenos_amarillo": "⚠️ Возможная неисправность датчиков EBS / датчиков скорости колёс",
        "frenos_rojo": "🔴 Потеря воздуха / электрическая неисправность",
        "radar_amarillo": "⚠️ Ошибка калибровки / смещение радара / повреждение радара",
        "radar_rojo": "🔴 Дефект радара / электрическая неисправность",
        "caja_amarillo": "⚠️ Электрическая неисправность / соленоидный клапан",
        "caja_rojo": "🔴 Утечка воздуха / блокировка ЭБУ",
        "menu": "Выберите услугу:",
        "coincidencias": "🔎 Найдено {n} совпадений:\n\n{lista}\n\nВведите *полный* код. Пример: `111 FMI 1`",
    },
}

def get_lang(update):
    """Detecta el idioma del usuario desde Telegram."""
    lang = update.effective_user.language_code or "es"
    lang = lang[:2].lower()
    if lang not in TEXTOS:
        lang = "en"
    return lang

def t(update, key, **kwargs):
    """Devuelve el texto en el idioma del usuario."""
    lang = get_lang(update)
    texto = TEXTOS[lang].get(key, TEXTOS["es"].get(key, key))
    if kwargs:
        texto = texto.format(**kwargs)
    return texto

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
    "white smoke":    "Possible faulty injector / head gasket / compression loss",
    "fumée blanche":  "Possible injecteur défaillant / joint de culasse / perte de compression",
    "fumo branco":    "Possível injetor avariado / junta da cabeça / perda de compressão",
    "белый дым":      "Возможно: неисправный инжектор / прокладка головки / потеря компрессии",
    "humo negro":     "Exceso combustible: inyectores / turbo / EGR bloqueado / MAF",
    "black smoke":    "Excess fuel: injectors / turbo / blocked EGR / MAF",
    "fumée noire":    "Excès de carburant: injecteurs / turbo / EGR bloqué / MAF",
    "fumo preto":     "Excesso combustível: injetores / turbo / EGR bloqueado / MAF",
    "чёрный дым":     "Избыток топлива: инжекторы / турбо / заблокирован EGR / MAF",
    "falta potencia": "Revisar: turbo / filtro aire / EGR / sistema combustible",
    "lack of power":  "Check: turbo / air filter / EGR / fuel system",
    "manque de puissance": "Vérifier: turbo / filtre à air / EGR / système carburant",
    "falta de potência": "Verificar: turbo / filtro de ar / EGR / sistema combustível",
    "потеря мощности": "Проверить: турбо / воздушный фильтр / EGR / топливная система",
    "no arranca":     "Revisar: batería / motor arranque / combustible / sensor régimen",
    "won't start":    "Check: battery / starter motor / fuel / crankshaft sensor",
    "ne démarre pas": "Vérifier: batterie / démarreur / carburant / capteur vilebrequin",
    "não arranca":    "Verificar: bateria / motor de arranque / combustível / sensor",
    "не заводится":   "Проверить: аккумулятор / стартер / топливо / датчик коленвала",
    "tirones":        "Revisar: inyección / sensores MAF-MAP / filtro aire",
    "misfiring":      "Check: injection / MAF-MAP sensors / air filter",
    "ratés":          "Vérifier: injection / capteurs MAF-MAP / filtre à air",
    "solavancos":     "Verificar: injeção / sensores MAF-MAP / filtro de ar",
    "рывки":          "Проверить: впрыск / датчики MAF-MAP / воздушный фильтр",
    "consumo alto":   "Revisar: MAF / inyección / turbo / EGR",
    "high consumption": "Check: MAF / injection / turbo / EGR",
    "consommation élevée": "Vérifier: MAF / injection / turbo / EGR",
    "consumo alto pt": "Verificar: MAF / injeção / turbo / EGR",
    "высокий расход": "Проверить: MAF / впрыск / турбо / EGR",
    "fallo adblue":   "Revisar: sistema SCR / inyector AdBlue / bomba / sensor NOx",
    "adblue fault":   "Check: SCR system / AdBlue injector / pump / NOx sensor",
    "défaut adblue":  "Vérifier: système SCR / injecteur AdBlue / pompe / capteur NOx",
    "falha adblue":   "Verificar: sistema SCR / injetor AdBlue / bomba / sensor NOx",
    "ошибка adblue":  "Проверить: система SCR / форсунка AdBlue / насос / датчик NOx",
    "ruido motor":    "Revisar: nivel aceite / presión aceite / distribución / cojinetes",
    "engine noise":   "Check: oil level / oil pressure / timing / bearings",
    "bruit moteur":   "Vérifier: niveau huile / pression huile / distribution / paliers",
    "ruído motor":    "Verificar: nível óleo / pressão óleo / distribuição / rolamentos",
    "шум двигателя":  "Проверить: уровень масла / давление масла / ГРМ / подшипники",
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
def btn_inicio(update, user_id=None):
    botones = [
        [InlineKeyboardButton(t(update, "iniciar"), callback_data="pagar_inicio")],
        [InlineKeyboardButton(t(update, "sintomas"), callback_data="pagar_sintoma")],
        [InlineKeyboardButton(t(update, "codigo"), callback_data="pagar_codigo")],
    ]
    if str(user_id) == str(ADMIN_ID):
        botones.append([InlineKeyboardButton(t(update, "estadisticas"), callback_data="stats")])
    return InlineKeyboardMarkup(botones)

def btn_si_no(update, base):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(update, "si"), callback_data=f"{base}_si"),
         InlineKeyboardButton(t(update, "no"), callback_data=f"{base}_no")]
    ])

def btn_tipo(update):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(update, "motor"), callback_data="motor")],
        [InlineKeyboardButton(t(update, "frenos"), callback_data="frenos")],
        [InlineKeyboardButton(t(update, "scr"), callback_data="scr")],
        [InlineKeyboardButton(t(update, "radar"), callback_data="radar")],
        [InlineKeyboardButton(t(update, "caja"), callback_data="caja")]
    ])

def btn_color(update):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(update, "amarillo"), callback_data="amarillo"),
         InlineKeyboardButton(t(update, "rojo"), callback_data="rojo")]
    ])

def btn_confirmar_pago(update, tipo):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(update, "ya_pagado"), callback_data=f"confirmar_{tipo}")],
        [InlineKeyboardButton(t(update, "volver"), callback_data="volver")]
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
    context.user_data["lang"] = get_lang(update)
    await update.effective_message.reply_text("...", reply_markup=ReplyKeyboardRemove())
    await update.effective_message.reply_text(
        t(update, "bienvenida"),
        parse_mode="Markdown",
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
    global stats
    q = update.callback_query
    await q.answer()
    d = q.data
    user_id = update.effective_user.id

    if d == "pagar_inicio":
        context.user_data.clear()
        await q.edit_message_text(
            t(update, "pagar_inicio", link=LINK_INICIO),
            parse_mode="Markdown",
            reply_markup=btn_confirmar_pago(update, "inicio")
        )

    elif d == "pagar_sintoma":
        context.user_data.clear()
        await q.edit_message_text(
            t(update, "pagar_sintoma", link=LINK_SINTOMA),
            parse_mode="Markdown",
            reply_markup=btn_confirmar_pago(update, "sintoma")
        )

    elif d == "pagar_codigo":
        context.user_data.clear()
        await q.edit_message_text(
            t(update, "pagar_codigo", link=LINK_CODIGO),
            parse_mode="Markdown",
            reply_markup=btn_confirmar_pago(update, "codigo")
        )

    elif d.startswith("confirmar_"):
        tipo = d.split("_")[1]
        context.user_data["esperando_email"] = tipo
        await q.edit_message_text(t(update, "pedir_email"), parse_mode="Markdown")

    elif d == "inicio_verificado":
        await q.edit_message_text(t(update, "testigo"), reply_markup=btn_si_no(update, "testigo"))

    elif d == "testigo_si":
        await q.edit_message_text(t(update, "tipo_testigo"), reply_markup=btn_tipo(update))

    elif d == "testigo_no":
        context.user_data["modo_sintomas_libre"] = True
        await q.edit_message_text(t(update, "intro_sintoma"), parse_mode="Markdown")

    elif d in ["motor", "frenos", "scr", "radar", "caja"]:
        context.user_data["tipo"] = d
        await q.edit_message_text(t(update, "color_testigo"), reply_markup=btn_color(update))

    elif d == "amarillo" and context.user_data.get("tipo") == "motor":
        await q.edit_message_text(t(update, "limitado"), reply_markup=btn_si_no(update, "lim"))

    elif d == "lim_si":
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

    elif d == "amarillo" and context.user_data.get("tipo") == "radar":
        await q.edit_message_text(t(update, "radar_amarillo"))
        await lanzar_encuesta(q.message, update)

    elif d == "rojo" and context.user_data.get("tipo") == "radar":
        await q.edit_message_text(t(update, "radar_rojo"))
        await lanzar_encuesta(q.message, update)

    elif d == "amarillo" and context.user_data.get("tipo") == "caja":
        await q.edit_message_text(t(update, "caja_amarillo"))
        await lanzar_encuesta(q.message, update)

    elif d == "rojo" and context.user_data.get("tipo") == "caja":
        await q.edit_message_text(t(update, "caja_rojo"))
        await lanzar_encuesta(q.message, update)

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
            f"📊 *Estadísticas IVECO*\n\n"
            f"Usos totales: {stats['usos']}\n"
            f"Usuarios únicos: {len(stats['usuarios'])}\n"
            f"Códigos consultados: {len(codigos)}\n\n"
            f"💶 *Ingresos estimados: {ingresos}€*\n"
            f"  Inicio: {stats['ingresos_inicio']} consultas\n"
            f"  Síntoma: {stats['ingresos_sintoma']} consultas\n"
            f"  Código: {stats['ingresos_codigo']} consultas"
            f"{top}"
        )
        await q.edit_message_text(texto, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(update, "volver"), callback_data="volver")]]))

    elif d == "volver":
        context.user_data.clear()
        await q.edit_message_text(t(update, "menu"), reply_markup=btn_inicio(update, user_id))

    elif d.startswith("enc1"):
        stats["facil_si" if "si" in d else "facil_no"] += 1
        guardar_stats(stats)
        await q.edit_message_text(t(update, "enc2"), reply_markup=btn_si_no(update, "enc2"))

    elif d.startswith("enc2"):
        stats["intuitivo_si" if "si" in d else "intuitivo_no"] += 1
        guardar_stats(stats)
        await q.edit_message_text(t(update, "enc3"), reply_markup=btn_si_no(update, "enc3"))

    elif d.startswith("enc3"):
        stats["util_si" if "si" in d else "util_no"] += 1
        guardar_stats(stats)
        await q.edit_message_text(t(update, "enc_fin"), reply_markup=btn_inicio(update, user_id))

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

        await update.message.reply_text(t(update, "verificando"))
        pagado = verificar_pago(email, link)

        if pagado:
            context.user_data["pagado"] = tipo
            if tipo == "inicio":
                stats["ingresos_inicio"] += 1
                guardar_stats(stats)
                await update.message.reply_text(
                    t(update, "pago_ok"),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(t(update, "continuar"), callback_data="inicio_verificado")]
                    ])
                )
            elif tipo == "sintoma":
                stats["ingresos_sintoma"] += 1
                guardar_stats(stats)
                context.user_data["modo_sintomas"] = True
                await update.message.reply_text(
                    t(update, "pago_ok") + "\n\n" + t(update, "intro_sintoma"),
                    parse_mode="Markdown"
                )
            elif tipo == "codigo":
                stats["ingresos_codigo"] += 1
                guardar_stats(stats)
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
                    [InlineKeyboardButton(t(update, "volver"), callback_data="volver")]
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
                t(update, "codigo_no_encontrado"), parse_mode="Markdown"
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
                t(update, "sintoma_no_encontrado"), parse_mode="Markdown"
            )
        await lanzar_encuesta(update.message, update)
        return

    await update.message.reply_text(t(update, "menu"), reply_markup=btn_inicio(update, user_id))

# =====================================================================
# APP
# =====================================================================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(botones))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto))

print("✅ Bot IVECO Multiidioma OK 🚛")
app.run_polling(drop_pending_updates=True)
