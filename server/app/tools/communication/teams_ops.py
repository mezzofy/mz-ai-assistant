"""
Teams Tool — MS Graph API for Microsoft Teams messaging.

Tools provided:
    teams_post_message  — Post a message to a Teams channel
    teams_send_dm       — Send a direct message to a Teams user
    teams_list_channels — List available channels in the Mezzofy team
    teams_read_messages — Read recent messages from a channel

Config required (config.yaml → teams):
    team_id, channels (dict of name → channel_id)

MS Graph permissions required:
    Team.ReadBasic.All, ChannelMessage.Send, Chat.ReadWrite, Files.ReadWrite.All
"""

import logging
from typing import Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.teams")

# MS Graph base URL
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class TeamsOps(BaseTool):
    """Microsoft Teams operations via MS Graph API."""

    def __init__(self, config: dict):
        super().__init__(config)
        teams_cfg = config.get("teams", {})
        ms365_cfg = config.get("ms365", {})
        self._team_id: str = teams_cfg.get("team_id", "")
        self._channels: dict = teams_cfg.get("channels", {})
        self._bot_name: str = teams_cfg.get("bot_name", "MezzofyAI")
        self._tenant_id: str = ms365_cfg.get("tenant_id", "")
        self._client_id: str = ms365_cfg.get("client_id", "")
        self._client_secret: str = ms365_cfg.get("client_secret", "")
        self._sender_user_id: str = teams_cfg.get("sender_user_id", "")

    def _get_client(self):
        """Create an async MS Graph client using client credentials."""
        from azure.identity.aio import ClientSecretCredential
        from msgraph import GraphServiceClient

        credential = ClientSecretCredential(
            tenant_id=self._tenant_id,
            client_id=self._client_id,
            client_secret=self._client_secret,
        )
        return GraphServiceClient(credential)

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "teams_post_message",
                "description": (
                    "Post a message to a Microsoft Teams channel. Supports plain text "
                    "and HTML-formatted content. Use this to notify teams of events, "
                    "share reports, or broadcast updates to a department channel."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel_name": {
                            "type": "string",
                            "description": (
                                "Channel to post to. One of: general, sales, finance, "
                                "marketing, support, management."
                            ),
                            "enum": ["general", "sales", "finance", "marketing", "support", "management"],
                        },
                        "content": {
                            "type": "string",
                            "description": "Message content. Supports HTML formatting.",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Optional message subject/headline (displayed above content).",
                        },
                    },
                    "required": ["channel_name", "content"],
                },
                "handler": self._post_message,
            },
            {
                "name": "teams_send_dm",
                "description": (
                    "Send a direct message (DM) to a specific Teams user by their email address. "
                    "Use for private notifications, task assignments, or one-on-one communication."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_email": {
                            "type": "string",
                            "description": "Email address of the Teams user to DM.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Message content. Supports HTML formatting.",
                        },
                    },
                    "required": ["user_email", "content"],
                },
                "handler": self._send_dm,
            },
            {
                "name": "teams_list_channels",
                "description": (
                    "List all available Teams channels in the Mezzofy team. "
                    "Returns channel names and their IDs."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                "handler": self._list_channels,
            },
            {
                "name": "teams_read_messages",
                "description": (
                    "Read recent messages from a Microsoft Teams channel. "
                    "Returns message content, sender, and timestamp."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel_name": {
                            "type": "string",
                            "description": "Channel to read. One of: general, sales, finance, marketing, support, management.",
                            "enum": ["general", "sales", "finance", "marketing", "support", "management"],
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of recent messages to return (default 20, max 50).",
                            "default": 20,
                        },
                    },
                    "required": ["channel_name"],
                },
                "handler": self._read_messages,
            },
        ]

    async def _post_message(
        self,
        channel_name: str,
        content: str,
        subject: Optional[str] = None,
    ) -> dict:
        """Post a message to a Teams channel."""
        if not self._team_id:
            return self._err("Teams team_id is not configured.")

        channel_id = self._channels.get(channel_name)
        if not channel_id:
            return self._err(
                f"Unknown channel '{channel_name}'. "
                f"Available channels: {', '.join(self._channels.keys())}"
            )

        try:
            from msgraph.generated.teams.item.channels.item.messages.messages_request_builder import (
                MessagesRequestBuilder,
            )
            from msgraph.generated.models.chat_message import ChatMessage
            from msgraph.generated.models.item_body import ItemBody
            from msgraph.generated.models.body_type import BodyType
            from msgraph.generated.models.chat_message_importance import ChatMessageImportance

            client = self._get_client()

            message = ChatMessage()
            body = ItemBody()
            body.content_type = BodyType.Html
            body.content = content
            message.body = body

            if subject:
                message.subject = subject

            await (
                client.teams.by_team_id(self._team_id)
                .channels.by_channel_id(channel_id)
                .messages.post(body=message)
            )

            logger.info(f"Posted message to Teams channel #{channel_name}")
            return self._ok({
                "channel": channel_name,
                "content_preview": content[:200],
                "subject": subject,
            })

        except Exception as e:
            logger.error(f"Failed to post to Teams channel #{channel_name}: {e}")
            return self._err(str(e))

    async def _send_dm(self, user_email: str, content: str) -> dict:
        """Send a direct message to a Teams user."""
        if not self._tenant_id:
            return self._err("MS365 credentials are not configured.")
        if not self._sender_user_id:
            return self._err(
                "teams.sender_user_id is not configured. "
                "Set it to the Azure AD object ID of the DM sender user."
            )

        try:
            from msgraph.generated.models.chat import Chat
            from msgraph.generated.models.chat_type import ChatType
            from msgraph.generated.models.conversation_member import ConversationMember
            from msgraph.generated.models.aad_user_conversation_member import AadUserConversationMember
            from msgraph.generated.models.chat_message import ChatMessage
            from msgraph.generated.models.item_body import ItemBody
            from msgraph.generated.models.body_type import BodyType

            client = self._get_client()

            # Create or get existing 1:1 chat
            chat = Chat()
            chat.chat_type = ChatType.OneOnOne

            member1 = AadUserConversationMember()
            member1.odata_type = "#microsoft.graph.aadUserConversationMember"
            member1.roles = ["owner"]
            member1.additional_data = {
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_email}')"
            }

            # The sender/bot user also needs to be a member — use Azure AD user object ID
            member2 = AadUserConversationMember()
            member2.odata_type = "#microsoft.graph.aadUserConversationMember"
            member2.roles = ["owner"]
            member2.additional_data = {
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{self._sender_user_id}')"
            }

            chat.members = [member1, member2]
            created_chat = await client.chats.post(body=chat)
            chat_id = created_chat.id

            # Send the message
            message = ChatMessage()
            body = ItemBody()
            body.content_type = BodyType.Html
            body.content = content
            message.body = body

            await client.chats.by_chat_id(chat_id).messages.post(body=message)

            logger.info(f"Sent Teams DM to {user_email}")
            return self._ok({
                "recipient": user_email,
                "content_preview": content[:200],
            })

        except Exception as e:
            logger.error(f"Failed to send Teams DM to {user_email}: {e}")
            return self._err(str(e))

    async def _list_channels(self) -> dict:
        """List available Teams channels."""
        if not self._channels:
            return self._err("Teams channels are not configured.")

        channels = [
            {"name": name, "channel_id": channel_id}
            for name, channel_id in self._channels.items()
        ]
        return self._ok({
            "team_id": self._team_id,
            "channels": channels,
            "count": len(channels),
        })

    async def _read_messages(self, channel_name: str, limit: int = 20) -> dict:
        """Read recent messages from a Teams channel."""
        if not self._team_id:
            return self._err("Teams team_id is not configured.")

        channel_id = self._channels.get(channel_name)
        if not channel_id:
            return self._err(
                f"Unknown channel '{channel_name}'. "
                f"Available channels: {', '.join(self._channels.keys())}"
            )

        limit = min(limit, 50)

        try:
            from msgraph.generated.teams.item.channels.item.messages.messages_request_builder import (
                MessagesRequestBuilder,
            )

            client = self._get_client()

            query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
                top=limit,
                order_by=["createdDateTime desc"],
            )
            request_config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
                query_parameters=query_params,
            )

            response = await (
                client.teams.by_team_id(self._team_id)
                .channels.by_channel_id(channel_id)
                .messages.get(request_configuration=request_config)
            )

            messages = []
            if response and response.value:
                for msg in response.value:
                    sender_name = "Unknown"
                    if msg.from_ and msg.from_.user:
                        sender_name = msg.from_.user.display_name or msg.from_.user.id

                    content = ""
                    if msg.body:
                        content = msg.body.content or ""
                        # Strip basic HTML tags for plain text preview
                        import re
                        content = re.sub(r"<[^>]+>", "", content).strip()

                    messages.append({
                        "id": msg.id,
                        "sender": sender_name,
                        "content": content[:500],
                        "created_at": msg.created_date_time.isoformat() if msg.created_date_time else None,
                    })

            return self._ok({
                "channel": channel_name,
                "messages": messages,
                "count": len(messages),
            })

        except Exception as e:
            logger.error(f"Failed to read Teams messages from #{channel_name}: {e}")
            return self._err(str(e))
