import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import TELEGRAM_TOKEN

from biwenger import (
    obtener_ligas,
    obtener_informe,
    obtener_mercado_completo_datos,
    obtener_mercado_24h_datos,
    obtener_mercado_hoy_datos,
    obtener_miembros_liga,
    obtener_mercado_miembro_datos,
    obtener_ficha_jugador,
    obtener_jornadas,
    obtener_jornada,
    obtener_jornada_actual,
    _timestamp_partido,
)

from lineup_image import (
    LineupImageError,
    obtener_alineacion_mostrable,
    generar_imagen_alineacion,
)

from datetime import datetime
from zoneinfo import ZoneInfo

MADRID_TZ = ZoneInfo(
    "Europe/Madrid"
)

logging.basicConfig(
    level=logging.INFO
)

logger = logging.getLogger(
    __name__
)

MAX_TELEGRAM = 4000

POSICIONES_MERCADO_HOY = {
    "DL": {"boton": "DEL", "titulo": "⚽ DELANTEROS"},
    "MC": {"boton": "MC", "titulo": "🧠 MEDIOCENTROS"},
    "DF": {"boton": "DF", "titulo": "🛡️ DEFENSAS"},
    "PT": {"boton": "PT", "titulo": "🧤 PORTEROS"},
}
POSICIONES_MERCADO_HOY_ORDEN = ("DL", "MC", "DF", "PT")
POSICION_TODAS = "TODAS"
JUGADORES_POR_PAGINA = 6
JORNADAS_POR_PAGINA = 9


def teclado_jornadas(jornadas, pagina=0):
    if not isinstance(jornadas, list):
        jornadas = []
    total = len(jornadas)
    total_paginas = max(1, (total + JORNADAS_POR_PAGINA - 1) // JORNADAS_POR_PAGINA)
    try:
        pagina = int(pagina)
    except (TypeError, ValueError):
        pagina = 0
    pagina = max(0, min(pagina, total_paginas - 1))
    inicio = pagina * JORNADAS_POR_PAGINA
    fin = inicio + JORNADAS_POR_PAGINA
    jornadas_pagina = jornadas[inicio:fin]
    botones = []
    fila = []
    for jornada in jornadas_pagina:
        if not isinstance(jornada, dict):
            continue
        jornada_id = jornada.get("id")
        short = jornada.get("short", "J?")
        if jornada_id is None:
            continue
        fila.append(InlineKeyboardButton(str(short), callback_data=f"jornada:{jornada_id}:todas"))
        if len(fila) == 3:
            botones.append(fila)
            fila = []
    if fila:
        botones.append(fila)
    fila_paginacion = []
    if pagina > 0:
        fila_paginacion.append(InlineKeyboardButton("◀️", callback_data=f"jornadas:pagina:{pagina - 1}"))
    fila_paginacion.append(InlineKeyboardButton(f"{pagina + 1}/{total_paginas}", callback_data="noop"))
    if pagina < total_paginas - 1:
        fila_paginacion.append(InlineKeyboardButton("▶️", callback_data=f"jornadas:pagina:{pagina + 1}"))
    botones.append(fila_paginacion)
    return InlineKeyboardMarkup(botones)


def _datos_boton_jugador(player_id, player_name, equipo=None, posicion=None):
    return player_name, equipo or "?", posicion or "?"


def boton_jugador(player_id, player_name, equipo=None, posicion=None):
    if player_id is None:
        return None
    nombre, equipo, posicion = _datos_boton_jugador(player_id, player_name, equipo, posicion)
    return InlineKeyboardButton(f"⚽ {nombre} [{equipo}] ({posicion})", callback_data=f"jugador:{player_id}")


def boton_jugador_mercado(venta):
    return boton_jugador(venta.get("player_id"), venta.get("player_name", "Jugador"), venta.get("team", "?"), venta.get("position", "?"))


def _pagina_jugadores(jugadores, pagina=0):
    if not isinstance(jugadores, list):
        jugadores = []
    total = len(jugadores)
    total_paginas = max(1, (total + JUGADORES_POR_PAGINA - 1) // JUGADORES_POR_PAGINA)
    try:
        pagina = int(pagina)
    except (TypeError, ValueError):
        pagina = 0
    pagina = max(0, min(pagina, total_paginas - 1))
    inicio = pagina * JUGADORES_POR_PAGINA
    return jugadores[inicio:inicio + JUGADORES_POR_PAGINA], pagina, total_paginas


def _botones_jugadores_paginados(jugadores, pagina, callback_base):
    jugadores_pagina, pagina, total_paginas = _pagina_jugadores(jugadores, pagina)
    botones = []
    for jugador in jugadores_pagina:
        if not isinstance(jugador, dict):
            continue
        boton = boton_jugador(jugador.get("player_id"), jugador.get("player_name", "Jugador"), equipo=jugador.get("team"), posicion=jugador.get("position"))
        if boton is not None:
            botones.append([boton])
    fila_paginacion = []
    if pagina > 0:
        fila_paginacion.append(InlineKeyboardButton("◀️", callback_data=f"{callback_base}:{pagina - 1}"))
    fila_paginacion.append(InlineKeyboardButton(f"{pagina + 1}/{total_paginas}", callback_data="noop"))
    if pagina < total_paginas - 1:
        fila_paginacion.append(InlineKeyboardButton("▶️", callback_data=f"{callback_base}:{pagina + 1}"))
    botones.append(fila_paginacion)
    return botones


async def noop_callback(update, context):
    await update.callback_query.answer()


def teclado_menu_liga():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Informe", callback_data="menu:informe")],
        [InlineKeyboardButton("🔄 Mercado", callback_data="menu:mercado")],
        [InlineKeyboardButton("📅 Jornadas", callback_data="menu:jornadas")],
        [InlineKeyboardButton("🏆 Cambiar liga", callback_data="menu:liga")],
    ])


def texto_menu_liga(context):
    nombre = context.user_data.get("liga_nombre", "Liga seleccionada")
    return f"🏆 {nombre}\n━━━━━━━━━━━━━━━━━━━━\n\nSelecciona una opción:"


async def mostrar_menu_liga(update, context):
    texto = texto_menu_liga(context)
    if update.message is not None:
        await update.message.reply_text(texto, reply_markup=teclado_menu_liga())
    elif update.callback_query is not None:
        await editar_mensaje(update.callback_query, texto, teclado_menu_liga())


def teclado_submenu_mercado():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Mercado completo", callback_data="mercado:completo")],
        [InlineKeyboardButton("📅 Mercado de hoy", callback_data="mercado:hoy")],
        [InlineKeyboardButton("⏱️ Mercado 24h", callback_data="mercado:24h")],
        [InlineKeyboardButton("🧑‍💼 Mercado por miembro", callback_data="mercado:miembro")],
        [InlineKeyboardButton("◀️ Volver", callback_data="menu:principal")],
    ])


def teclado_submenu_jornadas():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Jornada Actual", callback_data="jornadas:actual")],
        [InlineKeyboardButton("📚 Todas las Jornadas", callback_data="jornadas:todas")],
        [InlineKeyboardButton("◀️ Volver", callback_data="menu:principal")],
    ])


def texto_submenu_jornadas():
    return "📅 JORNADAS\n━━━━━━━━━━━━━━━━━━━━\n\nSelecciona una opción:"


async def mostrar_submenu_jornadas(update, context, editar=True):
    texto = texto_submenu_jornadas()
    teclado = teclado_submenu_jornadas()
    if update.callback_query is not None:
        if editar:
            await editar_mensaje(update.callback_query, texto, teclado)
        else:
            await update.callback_query.message.reply_text(texto, reply_markup=teclado)
        return
    if update.message is not None:
        await update.message.reply_text(texto, reply_markup=teclado)


async def mostrar_submenu_mercado(update, context, editar=True):
    texto = "🔄 MERCADO\n━━━━━━━━━━━━━━━━━━━━\n\nSelecciona una opción:"
    teclado = teclado_submenu_mercado()
    if update.callback_query is not None:
        if editar:
            await editar_mensaje(update.callback_query, texto, teclado)
        else:
            await update.callback_query.message.reply_text(texto, reply_markup=teclado)
        return
    if update.message is not None:
        await update.message.reply_text(texto, reply_markup=teclado)


async def start(update, context):
    liga_id = context.user_data.get("liga")
    if liga_id:
        await mostrar_menu_liga(update, context)
        return
    mensaje = await update.message.reply_text("🤖 ConsultasBiwenger\n━━━━━━━━━━━━━━━━━━━━\n\nPrimero selecciona una liga.")
    await mostrar_selector_liga(update, mensaje=mensaje)


async def mostrar_selector_liga(update, mensaje=None):
    ligas = obtener_ligas()
    botones = []
    for liga in ligas:
        if not isinstance(liga, dict):
            continue
        liga_id = liga.get("id")
        nombre = liga.get("name", f"Liga {liga_id}")
        if liga_id is None:
            continue
        botones.append([InlineKeyboardButton(str(nombre), callback_data=f"liga:{liga_id}")])
    if not botones:
        if mensaje is not None:
            await mensaje.edit_text("❌ No se encontraron ligas.")
        elif update.message is not None:
            await update.message.reply_text("❌ No se encontraron ligas.")
        return
    markup = InlineKeyboardMarkup(botones)
    texto = "🤖 ConsultasBiwenger\n━━━━━━━━━━━━━━━━━━━━\n\nPrimero selecciona una liga."
    if mensaje is not None:
        await mensaje.edit_text(texto, reply_markup=markup)
        return
    if update.callback_query is not None:
        await editar_mensaje(update.callback_query, texto, markup)
        return
    if update.message is not None:
        await update.message.reply_text(texto, reply_markup=markup)


async def liga(update, context):
    try:
        await mostrar_selector_liga(update)
    except Exception as exc:
        logger.exception("ERROR LIGA")
        await update.message.reply_text(f"Error obteniendo ligas:\n{exc}")


async def elegir_liga(update, context):
    query = update.callback_query
    await query.answer()
    try:
        if not query.data.startswith("liga:"):
            raise ValueError("Callback de liga inválido")
        liga_id = int(query.data.split(":", 1)[1])
        ligas = obtener_ligas()
        liga_encontrada = next((liga for liga in ligas if isinstance(liga, dict) and str(liga.get("id")) == str(liga_id)), None)
        if liga_encontrada is None:
            raise ValueError("La liga seleccionada ya no está disponible.")
        context.user_data["liga"] = liga_id
        context.user_data["liga_nombre"] = liga_encontrada.get("name", f"Liga {liga_id}")
        await editar_mensaje(query, texto_menu_liga(context), teclado_menu_liga())
    except Exception:
        logger.exception("ERROR ELEGIR LIGA")
        await editar_mensaje(query, "❌ No se pudo seleccionar la liga.")


def construir_texto_informe(report):
    texto = "📊 INFORME DE MANAGERS\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if not report:
        return texto + "No se han encontrado miembros en esta liga."
    managers = sorted(report.items(), key=lambda item: item[1].get("saldo_actual", 0), reverse=True)
    for manager, datos in managers:
        texto += (f"👤 {manager}\n"
                  f"⚽ Jugadores: {datos.get('numero_jugadores', 0)}\n"
                  f"🟢 Compras: {formatear_dinero(datos.get('total_compras', 0))}\n"
                  f"🔴 Ventas: {formatear_dinero(datos.get('total_ventas', 0))}\n"
                  f"💰 Saldo: {formatear_dinero(datos.get('saldo_actual', 0))}\n"
                  f"💵 Puja máxima: {formatear_dinero(datos.get('puja_maxima', 0))}\n\n")
    return texto.rstrip()


def teclado_volver_principal():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Volver", callback_data="menu:principal")]])


async def informe(update, context):
    liga_id = await comprobar_liga(update, context)
    if not liga_id:
        return
    try:
        mensaje_carga = await update.message.reply_text("📊 Calculando informe...")
        report = obtener_informe(liga_id)
        texto = construir_texto_informe(report)
        botones = teclado_con_fijar(teclado_volver_principal())
        if len(texto) <= MAX_TELEGRAM:
            await mensaje_carga.edit_text(texto, reply_markup=botones)
        else:
            await mensaje_carga.delete()
            partes = [texto[i:i + MAX_TELEGRAM] for i in range(0, len(texto), MAX_TELEGRAM)]
            for parte in partes[:-1]:
                await update.message.reply_text(parte)
            await update.message.reply_text(partes[-1].rstrip(), reply_markup=botones)
    except Exception as exc:
        logger.exception("ERROR INFORME")
        await update.message.reply_text(f"Error calculando informe:\n{exc}")


async def comprobar_liga(update, context):
    liga_id = context.user_data.get("liga")
    if not liga_id:
        if update.message is not None:
            await update.message.reply_text("Primero selecciona una liga con /liga")
        elif update.callback_query is not None:
            await update.callback_query.answer("Primero selecciona una liga.", show_alert=True)
        return None
    return int(liga_id)


def _nombre_equipo(valor, defecto):
    if isinstance(valor, dict):
        return valor.get("name") or valor.get("shortName") or str(valor.get("id") or defecto)
    return str(valor or defecto)


async def mostrar_ficha_partido(query, context, jornada, partido):
    home_raw = partido.get("home", "Local")
    away_raw = partido.get("away", "Visitante")
    home_name = _nombre_equipo(home_raw, "Local")
    away_name = _nombre_equipo(away_raw, "Visitante")

    timestamp = _timestamp_partido(partido)
    if timestamp is not None:
        fecha_partido = datetime.fromtimestamp(timestamp, tz=MADRID_TZ)
        traducciones_dia = {"Mon": "Lun", "Tue": "Mar", "Wed": "Mié", "Thu": "Jue", "Fri": "Vie", "Sat": "Sáb", "Sun": "Dom"}
        dia = traducciones_dia.get(fecha_partido.strftime("%a"), fecha_partido.strftime("%a"))
        fecha = f"{dia} {fecha_partido.strftime('%d/%m')} · {fecha_partido.strftime('%H:%M')}"
    else:
        fecha = "Fecha pendiente"

    lineas = [
        f"⚽ {home_name} — {away_name}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🕐 {fecha}",
        "",
    ]

    # La imagen se genera a partir de los datos del partido actualizados.
    # Antes de la hora usa reports (once posible); después usa el once inicial.
    imagenes = []
    for team_key, opponent_raw in (("home", away_raw), ("away", home_raw)):
        team = partido.get(team_key)
        if not isinstance(team, dict):
            continue
        try:
            jugadores, confirmed = obtener_alineacion_mostrable(partido, team_key)
            if not jugadores:
                continue
            imagen = generar_imagen_alineacion(
                team,
                opponent=opponent_raw if isinstance(opponent_raw, dict) else {"name": _nombre_equipo(opponent_raw, "")},
                confirmed=confirmed,
                game=partido,
                team_key=team_key,
            )
            imagenes.append((team_key, imagen, confirmed))
        except LineupImageError as exc:
            logger.info("Sin alineación %s para partido %s: %s", team_key, partido.get("id"), exc)
        except Exception:
            logger.exception("ERROR GENERANDO IMAGEN ALINEACIÓN %s", team_key)

    estado = "11 inicial" if any(item[2] for item in imagenes) else "11 posible"
    lineas.extend([
        f"📋 Alineaciones: {estado}",
        "",
        "Selecciona una opción:",
    ])

    botones = [
        [InlineKeyboardButton("◀️ Volver a Partidos", callback_data=f"jornada:partidos:{jornada.get('id')}")],
        [InlineKeyboardButton("🔙 Volver a Jornada", callback_data=f"jornada:{jornada.get('id')}")],
    ]

    await editar_mensaje(query, "\n".join(lineas), teclado_con_fijar(InlineKeyboardMarkup(botones)))

    # Enviamos las imágenes como mensajes nuevos para que Telegram las renderice.
    # Así la ficha textual sigue siendo navegable y la imagen se puede reenviar.
    for team_key, imagen, confirmed in imagenes:
        try:
            caption = "11 inicial" if confirmed else "11 posible"
            await query.message.reply_photo(photo=InputFile(imagen), caption=caption)
        except Exception:
            logger.exception("ERROR ENVIANDO IMAGEN ALINEACIÓN %s", team_key)


# El resto del archivo conserva los handlers y funciones existentes.
