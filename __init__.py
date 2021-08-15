"""
Provides Python API for accessing Wasp web-based record management servers
"""
from .py_wasp import Wasp, FileValue, ReferenceValue, SystemInfo, ViewConfig, __version__

__all__ = ['Wasp', 'FileValue', 'ReferenceValue', 'SystemInfo', 'ViewConfig', '__version__']
