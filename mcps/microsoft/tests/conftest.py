"""Shared fixtures and mock data for Microsoft Graph tests."""

import pytest

# ---------------------------------------------------------------------------
# Sample Graph API response payloads
# ---------------------------------------------------------------------------

SAMPLE_USER_PROFILE = {
    "id": "user-id-001",
    "displayName": "John Carnahan",
    "mail": "jmcarny@gmail.com",
    "userPrincipalName": "jmcarny@gmail.com",
    "jobTitle": None,
}

SAMPLE_MAILBOX_SETTINGS = {
    "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('jmcarny.sbel%40outlook.com')/mailboxSettings",
    "timeZone": "Pacific Standard Time",
    "automaticRepliesSetting": {"status": "disabled"},
}

SAMPLE_MESSAGE = {
    "id": "AAMkAGI2TG93AAA=",
    "subject": "Weekly Report",
    "receivedDateTime": "2025-12-15T10:30:00Z",
    "isRead": False,
    "from": {
        "emailAddress": {
            "name": "Alice Smith",
            "address": "alice@example.com",
        }
    },
    "toRecipients": [
        {"emailAddress": {"name": "Bob Jones", "address": "bob@example.com"}}
    ],
    "body": {
        "contentType": "text",
        "content": "Here is the weekly report.\n\nBest,\nAlice",
    },
}

SAMPLE_MESSAGE_2 = {
    "id": "AAMkAGI2TG94BBB=",
    "subject": "Re: Project Update",
    "receivedDateTime": "2025-12-14T08:00:00Z",
    "isRead": True,
    "from": {
        "emailAddress": {
            "name": "Charlie Brown",
            "address": "charlie@example.com",
        }
    },
    "toRecipients": [
        {"emailAddress": {"name": "Bob Jones", "address": "bob@example.com"}}
    ],
    "body": {
        "contentType": "html",
        "content": "<p>Looks good!</p>",
    },
}

SAMPLE_MESSAGES_RESPONSE = {"value": [SAMPLE_MESSAGE, SAMPLE_MESSAGE_2]}

SAMPLE_TEAM = {
    "id": "team-id-001",
    "displayName": "Engineering",
    "description": "Engineering team",
}

SAMPLE_TEAM_2 = {
    "id": "team-id-002",
    "displayName": "Marketing",
    "description": "Marketing team",
}

SAMPLE_TEAMS_RESPONSE = {"value": [SAMPLE_TEAM, SAMPLE_TEAM_2]}

SAMPLE_CHANNEL = {
    "id": "channel-id-001",
    "displayName": "General",
    "description": "General channel",
}

SAMPLE_CHANNEL_2 = {
    "id": "channel-id-002",
    "displayName": "Random",
    "description": "Random channel",
}

SAMPLE_CHANNELS_RESPONSE = {"value": [SAMPLE_CHANNEL, SAMPLE_CHANNEL_2]}

SAMPLE_CHANNEL_MESSAGE = {
    "id": "msg-001",
    "body": {"content": "Hello from CLI"},
    "createdDateTime": "2025-12-15T12:00:00Z",
}

GRAPH_ERROR_403 = {
    "error": {
        "code": "Authorization_RequestDenied",
        "message": "Insufficient privileges to complete the operation.",
    }
}

GRAPH_ERROR_404 = {
    "error": {
        "code": "ResourceNotFound",
        "message": "Resource could not be discovered.",
    }
}

# ---------------------------------------------------------------------------
# Drive / File sample payloads
# ---------------------------------------------------------------------------

SAMPLE_DRIVE_ITEM_FILE = {
    "id": "file-id-001",
    "name": "report.csv",
    "size": 1024,
    "file": {"mimeType": "text/csv"},
    "lastModifiedDateTime": "2025-12-15T10:30:00Z",
    "lastModifiedBy": {
        "user": {"displayName": "Alice Smith", "id": "user-001"}
    },
    "webUrl": "https://onedrive.live.com/edit.aspx?resid=file-id-001",
    "parentReference": {
        "driveId": "drive-001",
        "path": "/drive/root:/Documents",
    },
}

SAMPLE_DRIVE_ITEM_FOLDER = {
    "id": "folder-id-001",
    "name": "Documents",
    "folder": {"childCount": 5},
    "lastModifiedDateTime": "2025-12-14T08:00:00Z",
    "lastModifiedBy": {
        "user": {"displayName": "Bob Jones", "id": "user-002"}
    },
    "webUrl": "https://onedrive.live.com/redir?resid=folder-id-001",
    "parentReference": {
        "driveId": "drive-001",
        "path": "/drive/root:",
    },
}

SAMPLE_DRIVE_ITEM_BINARY = {
    "id": "file-id-002",
    "name": "presentation.pptx",
    "size": 2_500_000,
    "file": {"mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "lastModifiedDateTime": "2025-12-13T15:00:00Z",
    "lastModifiedBy": {
        "user": {"displayName": "Charlie Brown", "id": "user-003"}
    },
    "webUrl": "https://onedrive.live.com/edit.aspx?resid=file-id-002",
    "parentReference": {
        "driveId": "drive-001",
        "path": "/drive/root:/Documents",
    },
}

SAMPLE_DRIVE_ITEM_LARGE_TEXT = {
    "id": "file-id-003",
    "name": "huge-log.txt",
    "size": 600_000,  # Exceeds 512 KB cap
    "file": {"mimeType": "text/plain"},
    "lastModifiedDateTime": "2025-12-12T09:00:00Z",
    "lastModifiedBy": {
        "user": {"displayName": "Alice Smith", "id": "user-001"}
    },
    "webUrl": "https://onedrive.live.com/edit.aspx?resid=file-id-003",
    "parentReference": {
        "driveId": "drive-001",
        "path": "/drive/root:",
    },
}

SAMPLE_DRIVE_CHILDREN_RESPONSE = {
    "value": [SAMPLE_DRIVE_ITEM_FOLDER, SAMPLE_DRIVE_ITEM_FILE, SAMPLE_DRIVE_ITEM_BINARY]
}

SAMPLE_SITE = {
    "id": "site-id-001",
    "displayName": "Engineering Hub",
    "name": "engineering",
    "webUrl": "https://contoso.sharepoint.com/sites/engineering",
}

SAMPLE_SITE_2 = {
    "id": "site-id-002",
    "displayName": "Marketing Portal",
    "name": "marketing",
    "webUrl": "https://contoso.sharepoint.com/sites/marketing",
}

SAMPLE_SITES_RESPONSE = {"value": [SAMPLE_SITE, SAMPLE_SITE_2]}

SAMPLE_SEARCH_RESPONSE = {
    "value": [
        {
            "hitsContainers": [
                {
                    "hits": [
                        {
                            "resource": {
                                "id": "search-file-001",
                                "name": "Q4-budget.xlsx",
                                "size": 45000,
                                "webUrl": "https://contoso.sharepoint.com/sites/finance/Q4-budget.xlsx",
                                "file": {"mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                                "lastModifiedDateTime": "2025-12-10T14:00:00Z",
                                "lastModifiedBy": {
                                    "user": {"displayName": "Finance Team"}
                                },
                            },
                            "summary": "Q4 <c0>budget</c0> projections for 2025",
                        },
                        {
                            "resource": {
                                "id": "search-file-002",
                                "name": "budget-notes.md",
                                "size": 2048,
                                "webUrl": "https://contoso.sharepoint.com/sites/finance/budget-notes.md",
                                "file": {"mimeType": "text/markdown"},
                                "lastModifiedDateTime": "2025-12-09T11:00:00Z",
                                "lastModifiedBy": {
                                    "user": {"displayName": "Alice Smith"}
                                },
                            },
                            "summary": "Notes on <c0>budget</c0> review meeting",
                        },
                    ],
                    "total": 2,
                    "moreResultsAvailable": False,
                }
            ],
            "searchTerms": ["budget"],
        }
    ]
}

SAMPLE_SEARCH_RESPONSE_EMPTY = {
    "value": [
        {
            "hitsContainers": [
                {
                    "hits": [],
                    "total": 0,
                    "moreResultsAvailable": False,
                }
            ],
            "searchTerms": ["nonexistent"],
        }
    ]
}


# ---------------------------------------------------------------------------
# Teams channel message payloads
# ---------------------------------------------------------------------------

SAMPLE_CHANNEL_MESSAGE_USER = {
    "id": "msg-user-001",
    "messageType": "message",
    "createdDateTime": "2025-12-15T12:00:00Z",
    "from": {"user": {"displayName": "Alice Smith"}, "application": None},
    "body": {"contentType": "text", "content": "Hello team!"},
    "attachments": [],
}

SAMPLE_CHANNEL_MESSAGE_BOT = {
    "id": "msg-bot-001",
    "messageType": "message",
    "createdDateTime": "2025-12-15T11:00:00Z",
    "from": {"application": {"displayName": "Power Automate"}, "user": None},
    "body": {"contentType": "html", "content": ""},
    "attachments": [
        {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": '{"type":"AdaptiveCard","body":[{"type":"TextBlock","text":"Build completed successfully"},{"type":"TextBlock","text":"Pipeline: main-deploy"}]}',
        }
    ],
}

SAMPLE_CHANNEL_MESSAGES_RESPONSE = {
    "value": [SAMPLE_CHANNEL_MESSAGE_USER, SAMPLE_CHANNEL_MESSAGE_BOT]
}


# ---------------------------------------------------------------------------
# Chat payloads
# ---------------------------------------------------------------------------

SAMPLE_CHAT_ONEONONE = {
    "id": "chat-1on1-001",
    "chatType": "oneOnOne",
    "topic": None,
    "lastUpdatedDateTime": "2025-12-15T14:00:00Z",
    "members": [
        {"displayName": "Alice Smith"},
        {"displayName": "Bob Jones"},
    ],
    "lastMessagePreview": {
        "createdDateTime": "2025-12-15T14:00:00Z",
        "body": {"content": "Sounds good!"},
        "from": {"user": {"displayName": "Alice Smith"}},
    },
}

SAMPLE_CHAT_GROUP = {
    "id": "chat-group-001",
    "chatType": "group",
    "topic": "Project Standup",
    "lastUpdatedDateTime": "2025-12-15T13:00:00Z",
    "members": [
        {"displayName": "Alice Smith"},
        {"displayName": "Bob Jones"},
        {"displayName": "Charlie Brown"},
    ],
    "lastMessagePreview": {
        "createdDateTime": "2025-12-15T13:00:00Z",
        "body": {"content": "Meeting at 3pm"},
        "from": {"user": {"displayName": "Bob Jones"}},
    },
}

SAMPLE_CHAT_MEETING = {
    "id": "chat-meeting-001",
    "chatType": "meeting",
    "topic": "Sprint Review",
    "lastUpdatedDateTime": "2025-12-15T10:00:00Z",
    "members": [
        {"displayName": "Alice Smith"},
        {"displayName": "Bob Jones"},
    ],
    "lastMessagePreview": {
        "createdDateTime": "2025-12-15T10:00:00Z",
        "body": {"content": "Notes attached"},
        "from": {"user": {"displayName": "Alice Smith"}},
    },
}

SAMPLE_CHATS_RESPONSE = {
    "value": [SAMPLE_CHAT_ONEONONE, SAMPLE_CHAT_GROUP, SAMPLE_CHAT_MEETING]
}

SAMPLE_CHAT_MESSAGES_RESPONSE = {
    "value": [SAMPLE_CHANNEL_MESSAGE_USER]
}

SAMPLE_CHAT_MESSAGE_SENT = {
    "id": "chat-msg-sent-001",
    "body": {"content": "Hello!"},
}
