"""V3-PLAN-01 positive client journey against the authoritative landing contract."""

from dataclasses import replace

import client
import pytest


@pytest.mark.parametrize("reported_ship_id, surface_opens", [(9, True), (8, False)])
def test_typed_landing_refreshes_player_and_active_ship_before_surface(
    ctx_factory, fake_conn, reported_ship_id, surface_opens
):
    """A confirmed landing is playable only after both owned refreshes agree."""
    ctx = ctx_factory(
        sector={"id": 17, "planets": [{"id": 77, "name": "Terra"}]}
    )
    ctx.hud = replace(ctx.hud, ship_id=8)
    fake_conn.queue("planet.land", {
        "status": "ok",
        "type": "planet.land.success",
        "data": {"planet_id": 77, "message": "Landed successfully."},
    })
    fake_conn.queue("player.my_info", {
        "status": "ok",
        "type": "player.info",
        "data": {"player": {"id": 3, "ship_id": 9, "turns_remaining": 39}},
    })
    fake_conn.queue("ship.status", {
        "status": "ok",
        "type": "ship.status",
        "data": {"ship": {"id": reported_ship_id, "onplanet": 77, "hull": 100}},
    })
    fake_conn.queue("move.describe_sector", {
        "status": "ok", "type": "sector.info", "data": {"sector_id": 17},
    })
    fake_conn.queue("planet.info", {
        "status": "ok",
        "type": "planet.info",
        "data": {"planet": {"planet_id": 77, "sector_id": 17}},
    })

    client.land_flow(ctx)

    assert ctx.state["on_planet"] is surface_opens
    assert ctx.state["current_planet_id"] == 77
    assert ctx.hud.turns_remaining == 39
    assert ctx.hud.ship_id == (9 if surface_opens else 8)
    assert ctx.menu_stack[-1] == ("SURFACE" if surface_opens else "MAIN")
    expected = ["planet.land", "player.my_info", "ship.status", "move.describe_sector"]
    if surface_opens:
        expected.append("planet.info")
    assert [call["command"] for call in fake_conn.calls] == expected
