"""Exercise GE Home's appliance-roster cleanup without cloud access."""

import asyncio
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from custom_components.ge_home import update_coordinator as coordinator_module


class RegistryCleanupTest(IsolatedAsyncioTestCase):
    async def test_roster_cleans_only_stale_devices_and_all_their_entities(self):
        """Query indexed ownership, preserving disabled entities and deletion order."""
        coordinator = object.__new__(coordinator_module.GeHomeUpdateCoordinator)
        coordinator.hass = object()
        coordinator._config_entry = SimpleNamespace(entry_id="ge-entry")
        coordinator._client = SimpleNamespace(appliances={"current-mac": object()})
        current_api = object()
        coordinator._appliance_apis = {"current-mac": current_api, "stale-mac": object()}
        coordinator._got_roster = False
        coordinator._all_initial_updates_received = asyncio.Event()
        coordinator._all_initial_updates_received.set()
        coordinator._async_maybe_trigger_all_ready = AsyncMock()

        stale = SimpleNamespace(
            id="stale", identifiers={("ge_home", "stale-mac")}, name="Stale"
        )
        current = SimpleNamespace(
            id="current", identifiers={("ge_home", "current-mac")}, name="Current"
        )
        no_ge_id = SimpleNamespace(
            id="no-ge-id", identifiers={("other", "unrelated-mac")}, name="Unrelated"
        )
        # Only provide removal methods. A full registry scan or deprecated
        # per-device config_entries access would fail this test.
        removed = Mock()
        devices = SimpleNamespace(async_remove_device=removed.device)
        entities = SimpleNamespace(async_remove=removed.entity)
        linked = [
            SimpleNamespace(entity_id="sensor.stale_enabled"),
            SimpleNamespace(entity_id="sensor.stale_disabled", disabled_by="user"),
        ]

        with (
            patch.object(coordinator_module.dr, "async_get", return_value=devices),
            patch.object(coordinator_module.er, "async_get", return_value=entities),
            patch.object(
                coordinator_module.dr,
                "async_entries_for_config_entry",
                return_value=[current, no_ge_id, stale],
            ) as by_config_entry,
            patch.object(
                coordinator_module.er, "async_entries_for_device", return_value=linked
            ) as by_device,
        ):
            await coordinator._on_appliance_list(None)

        by_config_entry.assert_called_once_with(devices, "ge-entry")
        by_device.assert_called_once_with(entities, "stale", include_disabled_entities=True)
        self.assertEqual(
            [(call[0], call[1]) for call in removed.mock_calls],
            [
                ("entity", ("sensor.stale_enabled",)),
                ("entity", ("sensor.stale_disabled",)),
                ("device", ("stale",)),
            ],
        )
        self.assertEqual(coordinator._appliance_apis, {"current-mac": current_api})
        coordinator._async_maybe_trigger_all_ready.assert_awaited_once_with(True)
