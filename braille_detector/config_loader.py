"""
Secure Configuration Loader for Braille Detection Module

This module provides secure path resolution and configuration management
without exposing hardcoded system paths.
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

class SecureConfigLoader:
    """Secure configuration loader with dynamic path resolution"""
    
    def __init__(self):
        # Get application base directory dynamically
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_dir = os.path.join(self.base_dir, "config")
        self.temp_dir = tempfile.gettempdir()
        
    def get_config_path(self, filename: str) -> str:
        """Get secure config file path"""
        return os.path.join(self.config_dir, filename)
    
    def ensure_config_dir(self) -> str:
        """Ensure config directory exists"""
        os.makedirs(self.config_dir, exist_ok=True)
        return self.config_dir
    
    def load_config(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load configuration from file safely"""
        try:
            config_path = self.get_config_path(filename)
            
            if not os.path.exists(config_path):
                return self.create_default_config(filename)
                
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # Set dynamic paths based on runtime environment
            config = self._resolve_dynamic_paths(config)
            
            return config
            
        except (json.JSONDecodeError, PermissionError, OSError) as e:
            print(f"[SecureConfigLoader] Config load error: {e}")
            return self.create_default_config(filename)
    
    def save_config(self, config: Dict[str, Any], filename: str) -> bool:
        """Save configuration to file safely"""
        try:
            self.ensure_config_dir()
            config_path = self.get_config_path(filename)
            
            # Sanitize paths before saving
            safe_config = self._sanitize_config_for_save(config)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(safe_config, f, indent=2)
                
            return True
            
        except (PermissionError, OSError) as e:
            print(f"[SecureConfigLoader] Config save error: {e}")
            return False
    
    def create_default_config(self, filename: str) -> Dict[str, Any]:
        """Create default configuration"""
        defaults = self._get_default_config()
        
        # Save the default config
        self.save_config(defaults, filename)
        
        return defaults
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return {
            "detection": {
                "min_confidence": 0.8,
                "stability_frames": 2,
                "debounce_ms": 200
            },
            "marker_tracking": {
                "aruco_id": 4,
                "fingertip_offset_ratio": -0.35
            },
            "image_processing": {
                "roi_scaling_factor": 2.5,
                "morphology_kernel_size": 3,
                "adaptive_thresh_block_size": 11,
                "adaptive_thresh_c": 2
            },
            "debug": {
                "enabled": False,
                "directory": os.path.join(self.temp_dir, "braille_debug")
            }
        }
    
    def _resolve_dynamic_paths(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve relative paths to absolute paths safely"""
        resolved = config.copy()
        
        # Resolve debug directory
        if "debug" in resolved and "directory" in resolved["debug"]:
            debug_dir = resolved["debug"]["directory"]
            if not os.path.isabs(debug_dir):
                # Use temp directory as base for security
                resolved["debug"]["directory"] = os.path.join(self.temp_dir, "braille_debug")
        
        return resolved
    
    def _sanitize_config_for_save(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Remove or anonymize sensitive information before saving"""
        sanitized = config.copy()
        
        # Remove absolute paths and use relative paths only
        if "debug" in sanitized and "directory" in sanitized["debug"]:
            debug_dir = sanitized["debug"]["directory"]
            if os.path.isabs(debug_dir):
                sanitized["debug"]["directory"] = "./debug"
        
        return sanitized
    
    def get_debug_directory(self) -> str:
        """Get safe debug directory path"""
        debug_dir = os.path.join(self.temp_dir, "braille_debug")
        os.makedirs(debug_dir, exist_ok=True)
        return debug_dir
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration parameters"""
        try:
            # Check numeric ranges
            detection = config.get("detection", {})
            if detection.get("min_confidence", 0.0) < 0.0 or detection.get("min_confidence", 1.0) > 1.0:
                return False
                
            if detection.get("stability_frames", 1) < 1:
                return False
                
            # Check marker ID
            marker_tracking = config.get("marker_tracking", {})
            marker_id = marker_tracking.get("aruco_id", 4)
            if marker_id < 0 or marker_id > 1023:  # ArUco ID range
                return False
                
            return True
            
        except Exception:
            return False

# Global instance for import
config_loader = SecureConfigLoader()

def get_default_config() -> Dict[str, Any]:
    """Get default configuration"""
    return config_loader._get_default_config()

def load_braille_config() -> Dict[str, Any]:
    """Load braille detection configuration"""
    return config_loader.load_config("braille_config.json")

def save_braille_config(config: Dict[str, Any]) -> bool:
    """Save braille detection configuration"""
    return config_loader.save_config(config, "braille_config.json")
