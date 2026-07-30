from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS, DATA_KEY
from .coordinator import connection_key_for


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a (UI) config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and DATA_KEY in hass.data:
        connection_key = connection_key_for(entry.data)
        coordinator = hass.data[DATA_KEY].get(connection_key)
        if coordinator is not None:
            # Only tear down the (possibly shared) coordinator once the last
            # config entry using it has unloaded.
            coordinator.entry_ids.discard(entry.entry_id)
            if not coordinator.entry_ids:
                hass.data[DATA_KEY].pop(connection_key, None)
                await coordinator.async_shutdown()

    return unload_ok
