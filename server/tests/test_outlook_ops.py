"""
Tests for OutlookOps — import compatibility and tool registration.
These tests confirm the msgraph SDK import paths work with the installed version.
"""
import pytest


class TestOutlookOpsImports:
    """Confirm all msgraph imports used by OutlookOps resolve correctly."""

    def test_graph_client_import(self):
        """_get_graph_client imports must work (used by check_ms365_config)."""
        from azure.identity.aio import ClientSecretCredential  # noqa
        from msgraph import GraphServiceClient  # noqa

    def test_send_email_imports(self):
        """Imports used by _send_email must work."""
        from msgraph.generated.users.item.send_mail.send_mail_post_request_body import SendMailPostRequestBody  # noqa
        from msgraph.generated.models.message import Message  # noqa
        from msgraph.generated.models.item_body import ItemBody  # noqa
        from msgraph.generated.models.body_type import BodyType  # noqa
        from msgraph.generated.models.recipient import Recipient  # noqa
        from msgraph.generated.models.email_address import EmailAddress  # noqa

    def test_read_emails_imports(self):
        """Imports used by _read_emails — nested class pattern for msgraph-sdk==1.2.0."""
        from msgraph.generated.users.item.mail_folders.item.messages.messages_request_builder import MessagesRequestBuilder as MailFolderMessagesRequestBuilder  # noqa
        assert hasattr(MailFolderMessagesRequestBuilder, "MessagesRequestBuilderGetQueryParameters")
        assert hasattr(MailFolderMessagesRequestBuilder, "MessagesRequestBuilderGetRequestConfiguration")

    def test_search_emails_imports(self):
        """Imports used by _search_emails — nested class pattern."""
        from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder as UserMessagesRequestBuilder  # noqa
        assert hasattr(UserMessagesRequestBuilder, "MessagesRequestBuilderGetQueryParameters")
        assert hasattr(UserMessagesRequestBuilder, "MessagesRequestBuilderGetRequestConfiguration")

    def test_calendar_view_imports(self):
        """Imports used by _get_events — nested class pattern."""
        from msgraph.generated.users.item.calendar_view.calendar_view_request_builder import CalendarViewRequestBuilder  # noqa
        assert hasattr(CalendarViewRequestBuilder, "CalendarViewRequestBuilderGetQueryParameters")
        assert hasattr(CalendarViewRequestBuilder, "CalendarViewRequestBuilderGetRequestConfiguration")


class TestOutlookOpsTools:
    """OutlookOps registers expected tools without import errors."""

    def test_tools_registered(self):
        from app.tools.communication.outlook_ops import OutlookOps
        ops = OutlookOps(config={})
        tool_names = [t["name"] for t in ops.get_tools()]
        assert "outlook_send_email" in tool_names
        assert "outlook_read_emails" in tool_names
        assert "check_ms365_config" in tool_names
        assert "outlook_batch_send" in tool_names
        assert "outlook_reply_email" in tool_names
        assert "outlook_search_emails" in tool_names
        assert "outlook_create_event" in tool_names
        assert "outlook_get_events" in tool_names
        assert "outlook_find_free_slots" in tool_names
