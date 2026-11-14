"""
Session Manager for Udyam AI & Browser Automation
Maintains isolated browser contexts, controllers, and collected user data per session_id.
"""

import logging
from typing import Dict, Optional
from backend.controller import AutomationController

logger = logging.getLogger("session_manager")

class SessionManager:
    """Manages active AutomationController instances keyed by session_id."""

    def __init__(self):
        self._controllers: Dict[str, AutomationController] = {}

    def get_controller(self, session_id: str = "default_session") -> AutomationController:
        """Retrieves or creates an AutomationController for the given session_id."""
        if not session_id:
            session_id = "default_session"

        if session_id not in self._controllers:
            logger.info(f"Creating new AutomationController for session_id: {session_id}")
            self._controllers[session_id] = AutomationController(session_id=session_id)

        return self._controllers[session_id]

    def remove_session(self, session_id: str):
        """Removes a session and cleans up resources."""
        if session_id in self._controllers:
            controller = self._controllers.pop(session_id)
            logger.info(f"Removed session {session_id}")
            return controller
        return None

    async def stop_all(self):
        """Stops all active MCP clients across sessions on shutdown."""
        logger.info(f"Stopping all active sessions ({len(self._controllers)})...")
        for sid, ctrl in list(self._controllers.items()):
            try:
                await ctrl.mcp_client.stop()
            except Exception as e:
                logger.error(f"Error stopping session {sid}: {e}")
        self._controllers.clear()

# Global Singleton
session_manager = SessionManager()
