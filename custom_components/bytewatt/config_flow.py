"""Config flow for Byte-Watt integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .bytewatt_client import ByteWattClient
from .const import (
    DOMAIN, 
    CONF_USERNAME, 
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_NUMBER,
    CONF_SYSTEM_ID,
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
        self.inverters = []

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate the credentials
            self.client = ByteWattClient(
                self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            success = await self.client.initialize()

            if success:
                self.user_input = user_input
                return await self.async_step_inverter()
            else:
                errors["base"] = "auth"

        # Show the form
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
        if not self.inverters:
            self.inverters = await self.client.get_inverter_list()
            if not self.inverters:
                return self.async_abort(reason="no_inverters")

        configured_serials = [
            entry.data.get(CONF_SERIAL_NUMBER, "All")
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        ]

        if user_input is not None:
            serial_number = user_input[CONF_SERIAL_NUMBER]

            if serial_number in configured_serials:
                return self.async_abort(reason="already_configured")

            if serial_number == "All":
                system_id = ""
            else:
                inverter = next(
                    (inv for inv in self.inverters if inv["sysSn"] == serial_number), None
                )
                if inverter:
                    system_id = inverter.get("systemId")
                else:
                    # Handle case where inverter is not found (should not happen)
                    return self.async_abort(reason="inverter_not_found")
            
            self.user_input[CONF_SYSTEM_ID] = system_id
            self.user_input.update(user_input)
            title = (
                f"Byte-Watt ({self.user_input[CONF_USERNAME]}) - "
                f"{self.user_input.get(CONF_SERIAL_NUMBER, 'All')}"
            )
            return self.async_create_entry(
                title=title,
                data=self.user_input,
            )

        inverter_choices = {}
        if "All" not in configured_serials:
            inverter_choices["All"] = "All"

        if self.inverters:
            for inverter in self.inverters:
                if inverter['sysSn'] not in configured_serials:
                    inverter_choices[inverter['sysSn']] = inverter['sysSn']

        if not inverter_choices:
            return self.async_abort(reason="no_inverters_left")

        default_inverter = "All" if "All" in inverter_choices else next(iter(inverter_choices))
        return self.async_show_form(
            step_id="inverter",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERIAL_NUMBER, default=default_inverter): vol.In(
                        inverter_choices
                    ),
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