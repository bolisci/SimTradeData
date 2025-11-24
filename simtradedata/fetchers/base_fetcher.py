"""
Base fetcher class for all data fetchers

This module provides the base class with common login/logout/context manager
functionality to eliminate code duplication across fetchers.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    """
    Base class for all data fetchers

    Provides common functionality:
    - Login/logout state tracking
    - Context manager support (with statement)
    - Destructor cleanup
    - Error handling

    Subclasses only need to implement _do_login() and _do_logout()
    """

    def __init__(self):
        self._logged_in = False

    @abstractmethod
    def _do_login(self):
        """
        Subclass implements specific login logic

        Should raise ConnectionError if login fails
        """
        pass

    @abstractmethod
    def _do_logout(self):
        """
        Subclass implements specific logout logic

        Should handle cleanup of connections/resources
        """
        pass

    def login(self):
        """
        Login with state tracking

        Calls _do_login() if not already logged in
        """
        if not self._logged_in:
            self._do_login()
            self._logged_in = True
            logger.info(f"{self.__class__.__name__} login successful")

    def logout(self):
        """
        Logout with error handling

        Safely calls _do_logout() and handles any errors
        """
        if self._logged_in:
            try:
                self._do_logout()
            except Exception as e:
                logger.warning(f"{self.__class__.__name__} logout failed: {e}")
            finally:
                self._logged_in = False
                logger.info(f"{self.__class__.__name__} logout complete")

    def __enter__(self):
        """Context manager entry - login"""
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - logout"""
        self.logout()
        return False  # Don't suppress exceptions

    def __del__(self):
        """Destructor - ensure cleanup on object deletion"""
        try:
            self.logout()
        except:
            # Ignore all errors in destructor
            pass
