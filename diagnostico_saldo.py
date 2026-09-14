"""
Diagnóstico temporal del saldo del INFORME.

Uso:
    python diagnostico_saldo.py <liga_id>

NO modifica el saldo ni realiza operaciones en Biwenger.
Solo muestra qué cantidades está utilizando el bot
para calcular el saldo del INFORME.

Además:
- registra todas las llamadas a board_history()
- comprueba la paginación
- comprueba duplicados
- extrae las operaciones
- analiza específicamente BertetePorro
- cuenta compras y ventas
- muestra las operaciones de BertetePorro ordenadas por fecha
- reconstruye el saldo
"""

import sys
from collections import defaultdict

from biwenger import (
    _CLIENT,
    SALDO_INICIAL,
    _calcular_saldo_actual,
    _extraer_standings,
    _datos_standing,
)


NOMBRE_OBJETIVO = "BertetePorro"


def importe(valor):
    try:
        return f"{int(valor):,} €"
    except Exception:
        return f"{valor!r}"


def instalar_debug_paginacion():
    """
    Envuelve temporalmente _CLIENT.board_history() para mostrar
    cada petición y forzar la paginación real de Biwenger mediante
    offset + limit.

    Esto permite probar la paginación sin modificar biwenger.py.
    """

    original_board_history = _CLIENT.board_history

    contador = {
        "pagina": 0,
        "offset": 0,
    }

    def board_history_debug(league_id, date=None, limit=100):
        contador["pagina"] += 1
        pagina = contador["pagina"]
        offset = contador["offset"]

        print("\n" + "=" * 80)
        print(f"DEBUG PAGINACIÓN | PETICIÓN #{pagina}")
        print("=" * 80)

        print(f"league_id : {league_id}")
        print(f"offset    : {offset}")
        print(f"limit     : {limit}")
        print(f"date      : {date}  <-- IGNORADO EN ESTA PRUEBA")

        # Preparamos el contexto de liga igual que hace board_history().
        _CLIENT.prepare_context(league_id)

        # Probamos la paginación REAL de /board mediante offset.
        response = _CLIENT.get(
            f"/league/{_CLIENT.league_id}/board",
            params={
                "type": "transfer,market,bonus",
                "offset": offset,
                "limit": limit,
            },
        )

        data = (
            response.get("data", [])
            if isinstance(response, dict)
            else []
        )

        fechas = []

        for event in data:
            if not isinstance(event, dict):
                continue

            event_date = event.get("date")

            if isinstance(event_date, (int, float)):
                fechas.append(event_date)

        print(f"eventos recibidos: {len(data)}")

        if fechas:
            print(f"fecha MÁS NUEVA  : {max(fechas)}")
            print(f"fecha MÁS ANTIGUA: {min(fechas)}")
        else:
            print("No se encontraron fechas.")

        if data:
            print("\nPrimeros eventos de esta página:")

            for event in data[:3]:
                print(
                    f"  date={event.get('date')} "
                    f"type={event.get('type')!r} "
                    f"title={event.get('title')!r}"
                )

            print("\nÚltimos eventos de esta página:")

            for event in data[-3:]:
                print(
                    f"  date={event.get('date')} "
                    f"type={event.get('type')!r} "
                    f"title={event.get('title')!r}"
                )

        # Avanzamos por número real de eventos recibidos.
        contador["offset"] += len(data)

        return response

    _CLIENT.board_history = board_history_debug

    return contador


def analizar_berteteporro(operations):
    """
    Analiza exclusivamente las operaciones de BertetePorro.

    Datos esperados según el perfil de Biwenger:
        - 35 compras
        - 36 ventas

    También compara los importes con:
        - Compras: 137.048.154 €
        - Ventas: 95.230.700 €
    """

    print("\n" + "=" * 80)
    print(f"ANÁLISIS ESPECÍFICO: {NOMBRE_OBJETIVO}")
    print("=" * 80)

    compras = []
    ventas = []

    for op in operations:

        if not isinstance(op, dict):
            continue

        buyer = op.get("to")
        seller = op.get("from")

        to_name = (
            buyer.get("name")
            if isinstance(buyer, dict)
            else ""
        )

        from_name = (
            seller.get("name")
            if isinstance(seller, dict)
            else ""
        )

        if (
            to_name != NOMBRE_OBJETIVO
            and from_name != NOMBRE_OBJETIVO
        ):
            continue

        try:
            amount = int(op.get("amount", 0))
        except (TypeError, ValueError):
            amount = 0

        fecha = op.get("_event_date")
        titulo = op.get("_event_title", "")
        player_id = op.get("player")

        jugador = (
            op.get("player_name")
            or op.get("name")
            or op.get("player")
            or "?"
        )

        registro = {
            "fecha": fecha,
            "amount": amount,
            "titulo": titulo,
            "player_id": player_id,
            "jugador": jugador,
            "op": op,
        }

        if to_name == NOMBRE_OBJETIVO:
            compras.append(registro)

        if from_name == NOMBRE_OBJETIVO:
            ventas.append(registro)

    # Orden cronológico.
    compras.sort(
        key=lambda x: (
            x["fecha"]
            if isinstance(x["fecha"], (int, float))
            else 0
        )
    )

    ventas.sort(
        key=lambda x: (
            x["fecha"]
            if isinstance(x["fecha"], (int, float))
            else 0
        )
    )

    total_compras = sum(x["amount"] for x in compras)
    total_ventas = sum(x["amount"] for x in ventas)

    # ================================================================
    # RESUMEN
    # ================================================================

    print("\nRESUMEN BERTETEPORRO")
    print("-" * 80)

    print(f"Compras encontradas : {len(compras)}")
    print(f"Ventas encontradas  : {len(ventas)}")
    print(f"Total operaciones   : {len(compras) + len(ventas)}")

    print()
    print(f"Importe compras     : {importe(total_compras)}")
    print(f"Importe ventas      : {importe(total_ventas)}")

    # ================================================================
    # COMPARACIÓN CON BIWENGER
    # ================================================================

    compras_biwenger = 137_048_154
    ventas_biwenger = 95_230_700

    print("\nCOMPARACIÓN CON EL PERFIL DE BIWENGER")
    print("-" * 80)

    diferencia_compras = total_compras - compras_biwenger
    diferencia_ventas = total_ventas - ventas_biwenger

    print(f"Compras bot       : {importe(total_compras)}")
    print(f"Compras Biwenger  : {importe(compras_biwenger)}")
    print(f"Diferencia compras: {importe(diferencia_compras)}")

    print()

    print(f"Ventas bot        : {importe(total_ventas)}")
    print(f"Ventas Biwenger   : {importe(ventas_biwenger)}")
    print(f"Diferencia ventas : {importe(diferencia_ventas)}")

    # ================================================================
    # COMPROBACIÓN DE CONTEOS
    # ================================================================

    print("\nCOMPROBACIÓN DE CONTEOS")
    print("-" * 80)

    if len(compras) == 35:
        print("OK: el bot encuentra exactamente 35 COMPRAS.")
    else:
        print(
            f"ERROR: el bot encuentra {len(compras)} compras "
            f"(esperábamos 35)."
        )

    if len(ventas) == 36:
        print("OK: el bot encuentra exactamente 36 VENTAS.")
    else:
        print(
            f"ERROR: el bot encuentra {len(ventas)} ventas "
            f"(esperábamos 36)."
        )

    # ================================================================
    # COMPRAS
    # ================================================================

    print("\n" + "=" * 80)
    print("COMPRAS DE BERTETEPORRO")
    print("=" * 80)

    for numero, op in enumerate(compras, start=1):

        print(
            f"{numero:02d}. "
            f"fecha={op['fecha']} | "
            f"player={op['jugador']} | "
            f"player_id={op['player_id']} | "
            f"amount={importe(op['amount'])} | "
            f"title={op['titulo']!r}"
        )

    # ================================================================
    # VENTAS
    # ================================================================

    print("\n" + "=" * 80)
    print("VENTAS DE BERTETEPORRO")
    print("=" * 80)

    for numero, op in enumerate(ventas, start=1):

        print(
            f"{numero:02d}. "
            f"fecha={op['fecha']} | "
            f"player={op['jugador']} | "
            f"player_id={op['player_id']} | "
            f"amount={importe(op['amount'])} | "
            f"title={op['titulo']!r}"
        )

    # ================================================================
    # PRIMERA / ÚLTIMA OPERACIÓN
    # ================================================================

    todas = compras + ventas

    todas.sort(
        key=lambda x: (
            x["fecha"]
            if isinstance(x["fecha"], (int, float))
            else 0
        )
    )

    print("\n" + "=" * 80)
    print("PRIMERA Y ÚLTIMA OPERACIÓN DE BERTETEPORRO")
    print("=" * 80)

    if todas:

        primera = todas[0]
        ultima = todas[-1]

        print(
            f"PRIMERA | fecha={primera['fecha']} | "
            f"jugador={primera['jugador']} | "
            f"amount={importe(primera['amount'])} | "
            f"title={primera['titulo']!r}"
        )

        print(
            f"ÚLTIMA  | fecha={ultima['fecha']} | "
            f"jugador={ultima['jugador']} | "
            f"amount={importe(ultima['amount'])} | "
            f"title={ultima['titulo']!r}"
        )

    return total_compras, total_ventas

def extraer_bonificaciones(eventos):
    """
    Extrae ingresos extraordinarios de eventos type='bonus'.

    Ejemplo:
        {
            "type": "bonus",
            "content": [
                {
                    "user": {
                        "id": 14086223,
                        "name": "supersucio"
                    },
                    "amount": 250000,
                    "reason": "dailyStreak"
                }
            ],
            "date": 1788879450
        }

    Devuelve:
        {
            user_id: total_bonificaciones
        }
    """

    bonificaciones = defaultdict(int)
    detalles = defaultdict(list)

    for event in eventos:

        if not isinstance(event, dict):
            continue

        if event.get("type") != "bonus":
            continue

        fecha = event.get("date")

        content = event.get("content", [])

        if not isinstance(content, list):
            continue

        for item in content:

            if not isinstance(item, dict):
                continue

            user = item.get("user", {})

            if not isinstance(user, dict):
                continue

            user_id = user.get("id")
            nombre = user.get("name", "Desconocido")

            try:
                user_id = int(user_id)
            except (TypeError, ValueError):
                continue

            try:
                amount = int(item.get("amount", 0))
            except (TypeError, ValueError):
                amount = 0

            reason = item.get("reason", "desconocido")

            bonificaciones[user_id] += amount

            detalles[user_id].append({
                "fecha": fecha,
                "nombre": nombre,
                "amount": amount,
                "reason": reason,
            })

    print("\n" + "=" * 80)
    print("BONIFICACIONES")
    print("=" * 80)

    if not bonificaciones:
        print("No se encontraron eventos type='bonus'.")
        return bonificaciones

    for user_id in sorted(bonificaciones):

        total = bonificaciones[user_id]

        print(
            f"\nBONIFICACIONES | "
            f"user_id={user_id} | "
            f"total={importe(total)}"
        )

        lista = sorted(
            detalles[user_id],
            key=lambda x: (
                x["fecha"]
                if isinstance(x["fecha"], (int, float))
                else 0
            )
        )

        for bonus in lista:

            print(
                f"  - fecha={bonus['fecha']} | "
                f"usuario={bonus['nombre']!r} | "
                f"importe={importe(bonus['amount'])} | "
                f"reason={bonus['reason']!r}"
            )

    return bonificaciones

def main():

    if len(sys.argv) != 2:
        print("Uso: python diagnostico_saldo.py <liga_id>")
        raise SystemExit(2)

    liga_id = int(sys.argv[1])

    print("=" * 80)
    print("DIAGNÓSTICO SALDO INFORME")
    print(f"Liga: {liga_id}")
    print(f"Saldo inicial configurado: {importe(SALDO_INICIAL)}")
    print("=" * 80)

    # ================================================================
    # 1. STANDINGS
    # ================================================================

    print("\n" + "=" * 80)
    print("STANDINGS")
    print("=" * 80)

    league_response = _CLIENT.league(liga_id)
    standings_raw = _extraer_standings(league_response)

    standings = {}

    if isinstance(standings_raw, list):

        for miembro in standings_raw:

            datos = _datos_standing(miembro)

            nombre = datos.get("nombre", "Desconocido")

            standings[nombre] = datos

            print(
                f"STANDING | usuario={nombre!r} "
                f"| user_id={datos.get('id')} "
                f"| jugadores={datos.get('numero_jugadores')} "
                f"| valor_equipo={importe(datos.get('valor_equipo', 0))}"
            )

    print(f"\nUsuarios encontrados: {len(standings)}")

    # ================================================================
    # 2. HISTORIAL DE MERCADO
    # ================================================================

    print("\n" + "=" * 80)
    print("MOVIMIENTOS DE MERCADO")
    print("=" * 80)

    contador_paginas = instalar_debug_paginacion()

    history = _CLIENT.get_full_market_history(liga_id)

    print("\n" + "=" * 80)
    print("RESULTADO FINAL DE LA PAGINACIÓN")
    print("=" * 80)

    print(
        f"Total de peticiones board_history(): "
        f"{contador_paginas['pagina']}"
    )

    eventos = (
        history.get("data", [])
        if isinstance(history, dict)
        else []
    )

    bonificaciones = extraer_bonificaciones(eventos)

    print(f"Total de eventos descargados: {len(eventos)}")

    if eventos:

        fechas_totales = [
            e.get("date")
            for e in eventos
            if isinstance(e, dict)
            and isinstance(e.get("date"), (int, float))
        ]

        if fechas_totales:

            print(
                f"Fecha MÁS NUEVA global  : "
                f"{max(fechas_totales)}"
            )

            print(
                f"Fecha MÁS ANTIGUA global: "
                f"{min(fechas_totales)}"
            )

    # ================================================================
    # 2B. DUPLICADOS
    # ================================================================

    print("\n" + "=" * 80)
    print("COMPROBACIÓN DE DUPLICADOS")
    print("=" * 80)

    claves = defaultdict(list)

    for event in eventos:

        if not isinstance(event, dict):
            continue

        key = (
            event.get("date"),
            event.get("type"),
            event.get("title"),
        )

        claves[key].append(event)

    duplicados = {
        key: lista
        for key, lista in claves.items()
        if len(lista) > 1
    }

    print(f"Eventos totales   : {len(eventos)}")
    print(f"Claves únicas     : {len(claves)}")
    print(f"Claves duplicadas : {len(duplicados)}")

    if duplicados:

        print("\nPrimeros duplicados encontrados:")

        for key, lista in list(duplicados.items())[:20]:

            print(
                f"  clave={key!r} "
                f"| repeticiones={len(lista)}"
            )

    # ================================================================
    # 2C. OPERACIONES
    # ================================================================

    operations = _CLIENT.extract_operations(history)

    print("\n" + "=" * 80)
    print("OPERACIONES EXTRAÍDAS")
    print("=" * 80)

    print(f"Eventos descargados   : {len(eventos)}")
    print(f"Operaciones extraídas : {len(operations)}")

    market = defaultdict(
        lambda: {
            "compras": 0,
            "ventas": 0,
        }
    )

    market_counts = defaultdict(
        lambda: {
            "compras": 0,
            "ventas": 0,
        }
    )

    for op in operations:

        if not isinstance(op, dict):
            continue

        try:
            amount = int(op.get("amount", 0))
        except (TypeError, ValueError):
            amount = 0

        buyer = op.get("to")
        seller = op.get("from")

        player_id = op.get("player")
        event_date = op.get("_event_date")
        event_title = op.get("_event_title", "")

        # ------------------------------------------------------------
        # COMPRA
        # ------------------------------------------------------------

        if isinstance(buyer, dict):

            nombre = buyer.get("name", "Desconocido")

            market[nombre]["compras"] += amount
            market_counts[nombre]["compras"] += 1

            print(
                f"COMPRA | "
                f"usuario={nombre!r} | "
                f"player_id={player_id} | "
                f"importe={importe(amount)} | "
                f"fecha={event_date} | "
                f"titulo={event_title!r}"
            )

        # ------------------------------------------------------------
        # VENTA
        # ------------------------------------------------------------

        if isinstance(seller, dict):

            nombre = seller.get("name", "Desconocido")

            market[nombre]["ventas"] += amount
            market_counts[nombre]["ventas"] += 1

            print(
                f"VENTA   | "
                f"usuario={nombre!r} | "
                f"player_id={player_id} | "
                f"importe={importe(amount)} | "
                f"fecha={event_date} | "
                f"titulo={event_title!r}"
            )

    # ================================================================
    # 2D. ANÁLISIS BERTETEPORRO
    # ================================================================

    total_compras_bertete, total_ventas_bertete = (
        analizar_berteteporro(operations)
    )

    # ================================================================
    # 3. TOTALES DE MERCADO
    # ================================================================

    print("\n" + "=" * 80)
    print("TOTALES MERCADO")
    print("=" * 80)

    for nombre, datos in market.items():

        compras = datos["compras"]
        ventas = datos["ventas"]
        neto = ventas - compras

        print(
            f"MERCADO | "
            f"usuario={nombre!r} | "
            f"compras={importe(compras)} | "
            f"ventas={importe(ventas)} | "
            f"neto={importe(neto)} | "
            f"n_compras={market_counts[nombre]['compras']} | "
            f"n_ventas={market_counts[nombre]['ventas']}"
        )

    # ================================================================
    # 4. PREMIOS DE JORNADAS
    # ================================================================

    print("\n" + "=" * 80)
    print("PREMIOS DE JORNADAS")
    print("=" * 80)

    rewards = _CLIENT.get_round_rewards(liga_id)

    for user_id, total in sorted(rewards.items()):

        print(
            f"PREMIOS | "
            f"user_id={user_id} | "
            f"total={importe(total)}"
        )

    # ================================================================
    # 5. RECONSTRUCCIÓN DEL SALDO
    # ================================================================

    print("\n" + "=" * 80)
    print("RECONSTRUCCIÓN DEL SALDO")
    print("=" * 80)

    print(
        "FÓRMULA = SALDO_INICIAL + VENTAS - COMPRAS + PREMIOS + BONIFICACIONES"
    )

    nombres = set(standings) | set(market)

    for nombre in sorted(nombres):

        compras = int(
            market.get(nombre, {}).get("compras", 0)
        )

        ventas = int(
            market.get(nombre, {}).get("ventas", 0)
        )

        user_id = standings.get(nombre, {}).get("id")

        try:
            user_id_int = int(user_id)
        except (TypeError, ValueError):
            user_id_int = None

        premios = (
            int(rewards.get(user_id_int, 0))
            if user_id_int is not None
            else 0
        )

        bonificaciones_usuario = (
            int(bonificaciones.get(user_id_int, 0))
            if user_id_int is not None
            else 0
        )

        saldo_base = _calcular_saldo_actual(
            compras,
            ventas,
            premios,
        )

        saldo = saldo_base + bonificaciones_usuario

        print("\n" + "-" * 80)

        print(
            f"SALDO | usuario={nombre!r} | user_id={user_id}"
        )

        print(
            f"  1. Saldo inicial : {importe(SALDO_INICIAL)}"
        )

        print(
            f"  2. + Ventas      : {importe(ventas)}"
        )

        print(
            f"  3. - Compras     : {importe(compras)}"
        )

        print(
            f"  4. + Premios     : {importe(premios)}"
        )

        print(
            f"  5. + Bonificaciones: "
            f"{importe(bonificaciones_usuario)}"
        )

        print("  -------------------------------")

        print(
            f"     SALDO BOT     : {importe(saldo)}"
        )

    # ================================================================
    # 6. RESUMEN FINAL ESPECÍFICO
    # ================================================================

    print("\n" + "=" * 80)
    print("RESUMEN FINAL BERTETEPORRO")
    print("=" * 80)

    compras_bertete = market_counts[NOMBRE_OBJETIVO]["compras"]
    ventas_bertete = market_counts[NOMBRE_OBJETIVO]["ventas"]

    user_id_bertete = standings.get(
        NOMBRE_OBJETIVO,
        {}
    ).get("id")

    try:
        user_id_bertete = int(user_id_bertete)
    except (TypeError, ValueError):
        user_id_bertete = None

    premios_bertete = (
        int(rewards.get(user_id_bertete, 0))
        if user_id_bertete is not None
        else 0
    )

    bonificaciones_bertete = (
        int(bonificaciones.get(user_id_bertete, 0))
        if user_id_bertete is not None
        else 0
    )

    saldo_bertete_base = _calcular_saldo_actual(
        total_compras_bertete,
        total_ventas_bertete,
        premios_bertete,
    )

    saldo_bertete = (
        saldo_bertete_base
        + bonificaciones_bertete
    )

    print(
        f"Compras: {compras_bertete} "
        f"-> {importe(total_compras_bertete)}"
    )

    print(
        f"Ventas : {ventas_bertete} "
        f"-> {importe(total_ventas_bertete)}"
    )

    print(
        f"Premios: {importe(premios_bertete)}"
    )

    print(
        f"Bonificaciones: "
        f"{importe(bonificaciones_bertete)}"
    )

    print(
        f"Saldo calculado por bot: "
        f"{importe(saldo_bertete)}"
    )

    print("\n" + "=" * 80)
    print("FIN DIAGNÓSTICO")
    print("=" * 80)


if __name__ == "__main__":
    main()