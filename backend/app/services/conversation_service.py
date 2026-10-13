from ..ai.conversation import ConversationManager


_conversations: dict[str, ConversationManager] = {}


def get_conversation_manager(session_id: str) -> ConversationManager:
	"""Return the conversation manager associated with a session."""
	manager = _conversations.get(session_id)
	if manager is None:
		manager = ConversationManager()
		_conversations[session_id] = manager
	return manager


def reset_conversation(session_id: str) -> None:
	"""Discard a session's state so its next message starts a new conversation."""
	_conversations.pop(session_id, None)