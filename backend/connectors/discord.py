from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from backend.schemas import Event, EventType


# ============================================================
# ENVIRONMENT
# ============================================================

# Project root:
# C:\Users\mahen\OneDrive\Desktop\n8n
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env explicitly from project root.
load_dotenv(PROJECT_ROOT / ".env")


class DiscordConnector:
    """
    Discord REST API connector.

    Responsibilities:
    - Connect to Discord using a bot token
    - Discover Discord servers/channels
    - Fetch channel messages
    - Convert Discord messages into unified Event objects
    - Collect messages from all accessible text channels
    """

    BASE_URL = "https://discord.com/api/v10"

    # Discord channel types
    GUILD_TEXT_CHANNEL = 0
    GUILD_NEWS_CHANNEL = 5

    def __init__(
        self,
        token: str,
        *,
        timeout: int = 20,
    ):
        if not token:
            raise ValueError(
                "Discord bot token is required."
            )

        self.token = token
        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Authorization": f"Bot {token}",
                "Content-Type": "application/json",
                "User-Agent": "ContextRecoveryEngine/1.0",
            }
        )

    # ============================================================
    # HTTP REQUEST
    # ============================================================

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute a Discord REST API request.
        """

        url = f"{self.BASE_URL}{path}"

        response = self.session.request(
            method=method,
            url=url,
            params=params,
            timeout=self.timeout,
        )

        if not response.ok:
            try:
                error_data = response.json()
            except ValueError:
                error_data = response.text

            raise RuntimeError(
                f"Discord API request failed "
                f"(HTTP {response.status_code}): "
                f"{error_data}"
            )

        return response.json()

    # ============================================================
    # SERVER / GUILD
    # ============================================================

    def get_guild(
        self,
        guild_id: str,
    ) -> dict[str, Any]:
        """
        Get Discord server information.
        """

        if not guild_id:
            raise ValueError(
                "guild_id is required."
            )

        return self._request(
            "GET",
            f"/guilds/{guild_id}",
        )

    # ============================================================
    # CHANNEL DISCOVERY
    # ============================================================

    def get_guild_channels(
        self,
        guild_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get all channels from a Discord server
        that are accessible to the bot.
        """

        if not guild_id:
            raise ValueError(
                "guild_id is required."
            )

        return self._request(
            "GET",
            f"/guilds/{guild_id}/channels",
        )

    def get_text_channels(
        self,
        guild_id: str,
    ) -> list[dict[str, Any]]:
        """
        Return normal text and announcement channels.

        Discord channel types:
        0 = Guild Text Channel
        5 = Guild Announcement/News Channel
        """

        channels = self.get_guild_channels(
            guild_id
        )

        return [
            channel
            for channel in channels
            if channel.get("type")
            in {
                self.GUILD_TEXT_CHANNEL,
                self.GUILD_NEWS_CHANNEL,
            }
        ]

    # ============================================================
    # SINGLE CHANNEL
    # ============================================================

    def get_channel(
        self,
        channel_id: str,
    ) -> dict[str, Any]:
        """
        Get information about one Discord channel.
        """

        if not channel_id:
            raise ValueError(
                "channel_id is required."
            )

        return self._request(
            "GET",
            f"/channels/{channel_id}",
        )

    # ============================================================
    # MESSAGE FETCHING
    # ============================================================

    def get_messages(
        self,
        channel_id: str,
        *,
        limit: int = 100,
        before: str | None = None,
        after: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch messages from a Discord channel.

        Discord allows a maximum of 100 messages per request.
        """

        if not channel_id:
            raise ValueError(
                "channel_id is required."
            )

        if limit < 1:
            raise ValueError(
                "limit must be greater than 0."
            )

        limit = min(limit, 100)

        params: dict[str, Any] = {
            "limit": limit,
        }

        if before:
            params["before"] = before

        if after:
            params["after"] = after

        return self._request(
            "GET",
            f"/channels/{channel_id}/messages",
            params=params,
        )

    # ============================================================
    # MESSAGE → EVENT
    # ============================================================

    def message_to_event(
        self,
        message: dict[str, Any],
        *,
        project: str | None = None,
        channel_name: str | None = None,
    ) -> Event:
        """
        Convert one Discord message into the unified Event schema.
        """

        message_id = str(
            message.get("id", "")
        )

        if not message_id:
            raise ValueError(
                "Discord message is missing an id."
            )

        author = (
            message.get("author")
            or {}
        )

        actor = (
            author.get("global_name")
            or author.get("username")
            or author.get("id")
        )

        content = (
            message.get("content")
            or ""
        )

        timestamp = self._parse_timestamp(
            message.get("timestamp")
        )

        guild_id = message.get(
            "guild_id"
        )

        channel_id = message.get(
            "channel_id"
        )

        title = self._build_title(
            content=content,
            channel_name=channel_name,
        )

        references = (
            self._extract_references(
                message
            )
        )

        attachments = [
            {
                "id": attachment.get(
                    "id"
                ),
                "filename": attachment.get(
                    "filename"
                ),
                "url": attachment.get(
                    "url"
                ),
            }
            for attachment in message.get(
                "attachments",
                [],
            )
        ]

        return Event(
            id=f"discord_message_{message_id}",
            source="discord",
            source_id=message_id,
            event_type=EventType.MESSAGE,
            actor=actor,
            timestamp=timestamp,
            project=project,
            title=title,
            content=content,
            url=self._message_url(
                guild_id=guild_id,
                channel_id=channel_id,
                message_id=message_id,
            ),
            references=references,
            metadata={
                "message_id": message_id,
                "guild_id": guild_id,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "author_id": author.get(
                    "id"
                ),
                "author_username": author.get(
                    "username"
                ),
                "author_global_name": author.get(
                    "global_name"
                ),
                "edited_timestamp": message.get(
                    "edited_timestamp"
                ),
                "pinned": message.get(
                    "pinned",
                    False,
                ),
                "type": message.get(
                    "type"
                ),
                "attachments": attachments,
            },
        )

    # ============================================================
    # SINGLE CHANNEL COLLECTION
    # ============================================================

    def collect_messages(
        self,
        channel_id: str,
        *,
        limit: int = 100,
        project: str | None = None,
        channel_name: str | None = None,
    ) -> list[Event]:
        """
        Fetch messages from one channel
        and convert them into Event objects.
        """

        messages = self.get_messages(
            channel_id,
            limit=limit,
        )

        events = [
            self.message_to_event(
                message,
                project=project,
                channel_name=channel_name,
            )
            for message in messages
        ]

        events.sort(
            key=lambda event: event.timestamp,
            reverse=True,
        )

        return events

    # ============================================================
    # AUTOMATIC SERVER COLLECTION
    # ============================================================

    def collect_guild_messages(
        self,
        guild_id: str,
        *,
        limit_per_channel: int = 50,
        project: str | None = None,
    ) -> list[Event]:
        """
        Automatically collect messages from all
        accessible text channels in a Discord server.

        Flow:

        Server
           ↓
        Channels
           ↓
        Text Channels
           ↓
        Messages
           ↓
        Event[]
        """

        if not guild_id:
            raise ValueError(
                "guild_id is required."
            )

        if limit_per_channel < 1:
            raise ValueError(
                "limit_per_channel must be greater than 0."
            )

        channels = self.get_text_channels(
            guild_id
        )

        events: list[Event] = []

        for channel in channels:

            channel_id = channel.get(
                "id"
            )

            channel_name = channel.get(
                "name"
            )

            if not channel_id:
                continue

            try:

                channel_events = (
                    self.collect_messages(
                        channel_id,
                        limit=limit_per_channel,
                        project=project,
                        channel_name=channel_name,
                    )
                )

                events.extend(
                    channel_events
                )

            except RuntimeError:
                # Skip channels where the bot
                # does not have permission.
                continue

        events.sort(
            key=lambda event: event.timestamp,
            reverse=True,
        )

        return events

    # ============================================================
    # TIMESTAMP
    # ============================================================

    @staticmethod
    def _parse_timestamp(
        value: str | None,
    ) -> datetime:
        """
        Convert Discord ISO timestamp
        into timezone-aware datetime.
        """

        if not value:
            return datetime.now(
                timezone.utc
            )

        try:

            return datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )

        except ValueError:

            return datetime.now(
                timezone.utc
            )

    # ============================================================
    # TITLE
    # ============================================================

    @staticmethod
    def _build_title(
        *,
        content: str,
        channel_name: str | None,
    ) -> str:
        """
        Build a short event title.
        """

        text = " ".join(
            content.split()
        )

        if text:
            return text[:200]

        if channel_name:
            return (
                f"Message in #{channel_name}"
            )

        return "Discord message"

    # ============================================================
    # MESSAGE URL
    # ============================================================

    @staticmethod
    def _message_url(
        *,
        guild_id: str | None,
        channel_id: str | None,
        message_id: str,
    ) -> str | None:
        """
        Generate a clickable Discord message URL.
        """

        if not channel_id:
            return None

        guild_part = (
            guild_id
            or "@me"
        )

        return (
            "https://discord.com/channels/"
            f"{guild_part}/"
            f"{channel_id}/"
            f"{message_id}"
        )

    # ============================================================
    # REFERENCES
    # ============================================================

    @staticmethod
    def _extract_references(
        message: dict[str, Any],
    ) -> list[str]:
        """
        Extract reply and user-mention references.
        """

        references: list[str] = []

        # --------------------------------------------------------
        # Reply reference
        # --------------------------------------------------------

        referenced_message = (
            message.get(
                "message_reference"
            )
        )

        if referenced_message:

            referenced_id = (
                referenced_message.get(
                    "message_id"
                )
            )

            if referenced_id:

                references.append(
                    "discord_message:"
                    f"{referenced_id}"
                )

        # --------------------------------------------------------
        # Mentioned users
        # --------------------------------------------------------

        for user in message.get(
            "mentions",
            [],
        ):

            user_id = user.get(
                "id"
            )

            if user_id:

                references.append(
                    "discord_user:"
                    f"{user_id}"
                )

        return references

    # ============================================================
    # ENVIRONMENT
    # ============================================================

    @classmethod
    def from_env(
        cls,
    ) -> "DiscordConnector":
        """
        Create DiscordConnector using
        DISCORD_BOT_TOKEN from .env.
        """

        token = os.getenv(
            "DISCORD_BOT_TOKEN"
        )

        if not token:

            raise ValueError(
                "DISCORD_BOT_TOKEN is not configured."
            )

        return cls(token)