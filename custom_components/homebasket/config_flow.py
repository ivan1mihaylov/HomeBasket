"""Config flow for HomeBasket."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_ADD_UNKNOWN,
    CONF_EVENT_NAMES,
    CONF_LANGUAGE,
    CONF_TODO_ENTITY,
    CONF_USE_OPENFOODFACTS,
    DEFAULT_ADD_UNKNOWN,
    DEFAULT_EVENT_NAMES,
    DEFAULT_LANGUAGE,
    DEFAULT_USE_OPENFOODFACTS,
    DOMAIN,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the shared config/options schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_TODO_ENTITY, default=defaults.get(CONF_TODO_ENTITY, vol.UNDEFINED)
            ): EntitySelector(EntitySelectorConfig(domain="todo")),
            vol.Optional(
                CONF_USE_OPENFOODFACTS,
                default=defaults.get(CONF_USE_OPENFOODFACTS, DEFAULT_USE_OPENFOODFACTS),
            ): bool,
            vol.Optional(
                CONF_ADD_UNKNOWN,
                default=defaults.get(CONF_ADD_UNKNOWN, DEFAULT_ADD_UNKNOWN),
            ): bool,
            vol.Optional(
                CONF_LANGUAGE,
                default=defaults.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
            ): TextSelector(TextSelectorConfig()),
            vol.Optional(
                CONF_EVENT_NAMES,
                default=", ".join(
                    defaults.get(CONF_EVENT_NAMES, DEFAULT_EVENT_NAMES)
                    if isinstance(defaults.get(CONF_EVENT_NAMES), list)
                    else [defaults.get(CONF_EVENT_NAMES) or DEFAULT_EVENT_NAMES[0]]
                ),
            ): TextSelector(TextSelectorConfig()),
        }
    )


def _normalize(user_input: dict[str, Any]) -> dict[str, Any]:
    """Turn the comma separated event list into a real list."""
    data = dict(user_input)
    raw = data.get(CONF_EVENT_NAMES) or ""
    if isinstance(raw, str):
        data[CONF_EVENT_NAMES] = [part.strip() for part in raw.split(",") if part.strip()]
    if not data[CONF_EVENT_NAMES]:
        data[CONF_EVENT_NAMES] = list(DEFAULT_EVENT_NAMES)
    return data


class HomeBasketConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the to-do list and the lookup preferences."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="HomeBasket", data=_normalize(user_input)
            )

        return self.async_show_form(step_id="user", data_schema=_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HomeBasketOptionsFlow()


class HomeBasketOptionsFlow(OptionsFlow):
    """Let the user change the settings after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the options."""
        if user_input is not None:
            return self.async_create_entry(data=_normalize(user_input))

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(defaults))
