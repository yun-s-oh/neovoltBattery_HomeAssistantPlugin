"""Config flow for Byte-Watt integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .bytewatt_client import ByteWattClient
from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SERIAL_NUMBER,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL
)

_LOGGER = logging.getLogger(__name__)

class ByteWattConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Byte-Watt."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.client = None
        self.user_input = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self.client = ByteWattClient(self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            success = await self.client.initialize()

            if success:
                self.user_input = user_input
                return await self.async_step_inverter()
            else:
                errors["base"] = "auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                }
            ),
            errors=errors,
        )

    async def async_step_inverter(self, user_input=None):
        """Handle the inverter selection step."""
        if user_input is not None:
            self.user_input.update(user_input)
            return self.async_create_entry(
                title=f"Byte-Watt ({self.user_input[CONF_USERNAME]}) - {self.user_input.get(CONF_SERIAL_NUMBER, 'All')}",
                data=self.user_input,
            )

        inverters = await self.client.get_inverter_list()

        if not inverters:
            return self.async_abort(reason="no_inverters")

        inverter_choices = {"All": "All"}
        if inverters:
            for inverter in inverters:
                inverter_choices[inverter['sysSn']] = inverter['sysSn']

        return self.async_show_form(
            step_id="inverter",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL_NUMBER, default="All"): vol.In(inverter_choices),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ByteWattOptionsFlowHandler(config_entry)


class ByteWattOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Byte-Watt."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                }
            ),
        )
