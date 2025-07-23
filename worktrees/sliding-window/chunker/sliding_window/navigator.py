"""Window navigation implementation for traversing sliding windows."""

from typing import Optional, List, Union
import threading

from ..interfaces.sliding_window import (
    WindowNavigator,
    Window,
    SlidingWindowEngine
)


class DefaultWindowNavigator(WindowNavigator):
    """Default implementation of window navigation."""
    
    def __init__(self, engine: SlidingWindowEngine, text: str):
        """
        Initialize the navigator.
        
        Args:
            engine: The sliding window engine to use
            text: The text to navigate through
        """
        self.engine = engine
        self.text = text
        self._windows: List[Window] = []
        self._current_index = -1
        self._lock = threading.Lock()
        self._initialized = False
        
    def _ensure_initialized(self) -> None:
        """Ensure windows are generated (lazy initialization)."""
        with self._lock:
            if not self._initialized:
                self._windows = list(self.engine.process_text(self.text))
                self._initialized = True
                if self._windows:
                    self._current_index = 0
    
    def next_window(self) -> Optional[Window]:
        """Move to and return the next window."""
        self._ensure_initialized()
        
        with self._lock:
            if not self._windows:
                return None
            
            if self._current_index < len(self._windows) - 1:
                self._current_index += 1
                return self._windows[self._current_index]
            
            return None
    
    def previous_window(self) -> Optional[Window]:
        """Move to and return the previous window."""
        self._ensure_initialized()
        
        with self._lock:
            if not self._windows:
                return None
            
            if self._current_index > 0:
                self._current_index -= 1
                return self._windows[self._current_index]
            
            return None
    
    def jump_to_window(self, index: int) -> Optional[Window]:
        """Jump to a specific window by index."""
        self._ensure_initialized()
        
        with self._lock:
            if not self._windows or index < 0 or index >= len(self._windows):
                return None
            
            self._current_index = index
            return self._windows[self._current_index]
    
    def jump_to_position(self, position: int) -> Optional[Window]:
        """Jump to the window containing a specific position."""
        self._ensure_initialized()
        
        with self._lock:
            if not self._windows:
                return None
            
            # Binary search for efficiency
            left, right = 0, len(self._windows) - 1
            
            while left <= right:
                mid = (left + right) // 2
                window = self._windows[mid]
                
                if window.position.start <= position < window.position.end:
                    self._current_index = mid
                    return window
                elif position < window.position.start:
                    right = mid - 1
                else:
                    left = mid + 1
            
            # Position not found in any window
            return None
    
    def current_window(self) -> Optional[Window]:
        """Get the current window without moving."""
        self._ensure_initialized()
        
        with self._lock:
            if not self._windows or self._current_index < 0:
                return None
            
            return self._windows[self._current_index]
    
    def reset(self) -> None:
        """Reset navigation to the beginning."""
        with self._lock:
            self._current_index = 0 if self._windows else -1
    
    @property
    def total_windows(self) -> int:
        """Get the total number of windows."""
        self._ensure_initialized()
        return len(self._windows)
    
    @property
    def current_index(self) -> int:
        """Get the current window index."""
        return max(0, self._current_index)
    
    def has_next(self) -> bool:
        """Check if there's a next window."""
        self._ensure_initialized()
        return self._current_index < len(self._windows) - 1
    
    def has_previous(self) -> bool:
        """Check if there's a previous window."""
        return self._current_index > 0
    
    def get_window_range(self, start: int, end: Optional[int] = None) -> List[Window]:
        """Get a range of windows."""
        self._ensure_initialized()
        
        with self._lock:
            if not self._windows:
                return []
            
            if end is None:
                return self._windows[start:]
            
            return self._windows[start:end]
    
    def find_windows_containing(self, search_text: str, 
                               case_sensitive: bool = True) -> List[int]:
        """Find all windows containing the search text."""
        self._ensure_initialized()
        
        indices = []
        search_func = str.__contains__ if case_sensitive else str.lower().__contains__
        search_target = search_text if case_sensitive else search_text.lower()
        
        for i, window in enumerate(self._windows):
            content = window.content if case_sensitive else window.content.lower()
            if search_target in content:
                indices.append(i)
        
        return indices


class StreamingWindowNavigator(WindowNavigator):
    """Navigator for streaming window processing (doesn't load all windows into memory)."""
    
    def __init__(self, engine: SlidingWindowEngine, file_path: str, encoding: str = "utf-8"):
        """
        Initialize streaming navigator.
        
        Args:
            engine: The sliding window engine to use
            file_path: Path to the file to navigate
            encoding: File encoding
        """
        self.engine = engine
        self.file_path = file_path
        self.encoding = encoding
        self._current_window: Optional[Window] = None
        self._window_cache: dict = {}  # Limited cache of recent windows
        self._cache_size = 10
        self._lock = threading.Lock()
        
    def next_window(self) -> Optional[Window]:
        """Move to and return the next window."""
        with self._lock:
            if self._current_window is None:
                # Start from beginning
                generator = self.engine.process_file(self.file_path, self.encoding)
                try:
                    self._current_window = next(generator)
                    self._cache_window(self._current_window)
                    return self._current_window
                except StopIteration:
                    return None
            
            # Get next window based on current position
            target_index = self._current_window.position.window_index + 1
            
            # Check cache first
            if target_index in self._window_cache:
                self._current_window = self._window_cache[target_index]
                return self._current_window
            
            # Generate windows until we find the target
            for window in self.engine.process_file(self.file_path, self.encoding):
                if window.position.window_index == target_index:
                    self._current_window = window
                    self._cache_window(window)
                    return window
            
            return None
    
    def previous_window(self) -> Optional[Window]:
        """Move to and return the previous window."""
        with self._lock:
            if self._current_window is None or self._current_window.position.window_index == 0:
                return None
            
            target_index = self._current_window.position.window_index - 1
            
            # Check cache first
            if target_index in self._window_cache:
                self._current_window = self._window_cache[target_index]
                return self._current_window
            
            # Need to regenerate from beginning
            for window in self.engine.process_file(self.file_path, self.encoding):
                if window.position.window_index == target_index:
                    self._current_window = window
                    self._cache_window(window)
                    return window
            
            return None
    
    def jump_to_window(self, index: int) -> Optional[Window]:
        """Jump to a specific window by index."""
        with self._lock:
            # Check cache first
            if index in self._window_cache:
                self._current_window = self._window_cache[index]
                return self._current_window
            
            # Generate windows until we find the target
            for window in self.engine.process_file(self.file_path, self.encoding):
                if window.position.window_index == index:
                    self._current_window = window
                    self._cache_window(window)
                    return window
            
            return None
    
    def jump_to_position(self, position: int) -> Optional[Window]:
        """Jump to the window containing a specific position."""
        with self._lock:
            # Need to scan through windows
            for window in self.engine.process_file(self.file_path, self.encoding):
                if window.position.start <= position < window.position.end:
                    self._current_window = window
                    self._cache_window(window)
                    return window
            
            return None
    
    def current_window(self) -> Optional[Window]:
        """Get the current window without moving."""
        return self._current_window
    
    def reset(self) -> None:
        """Reset navigation to the beginning."""
        with self._lock:
            self._current_window = None
            self._window_cache.clear()
    
    def _cache_window(self, window: Window) -> None:
        """Add window to cache with size limit."""
        self._window_cache[window.position.window_index] = window
        
        # Remove oldest entries if cache is too large
        if len(self._window_cache) > self._cache_size:
            oldest_index = min(self._window_cache.keys())
            del self._window_cache[oldest_index]