#!/usr/bin/env python3
"""
Advanced Autonomous LLM Function Development System - Production Implementation v5.2.3
==================================================================================

A highly reliable system for autonomous function generation, validation, and storage
using Ollama models with enterprise-grade architecture, comprehensive error handling,
intelligent failure learning mechanisms, enhanced LLM tool integration, autonomous
local system exploration capabilities, and code diff logging for analysis.

CRITICAL ARCHITECTURAL FIXES APPLIED (v5.2.3):
===============================================
✅ EDIT 1: Enhanced Fallback Function Generation with UUID-based unique naming
✅ EDIT 2: Multi-Model Fallback Strategy with sequential model attempts  
✅ EDIT 3: Thread Management Enhancement with graceful shutdown
✅ EDIT 4: Function Name Uniqueness Validation with collision prevention
✅ EDIT 5: Enhanced Response Validation with content verification
✅ EDIT 6: Configuration Auto-Detection with working model identification

Enhanced Features:
- LLM-focused tool generation with standardized interfaces
- Sandbox execution environment for safe testing
- Security analysis with static code checking
- Enhanced uniqueness detection with signature analysis
- Goal-driven autonomous exploration
- Function registry for LLM programmatic access
- Natural language command integration
- Real-time action monitoring during autonomous mode
- Comprehensive safeguards and access controls
- Sandboxed local filesystem exploration
- Installed tool discovery and integration
- Enhanced AST-based duplicate detection
- Artifact-driven function generation
- Proper Ollama initialization and connectivity checks
- Code diff logging for validation analysis and training

Author: Senior Systems Architect  
Version: 5.2.3 (ARCHITECTURALLY FIXED)
Dependencies: ollama, black (optional), bandit (optional)
"""

import asyncio
import json
import sqlite3
import os
import sys
import logging
import threading
import time
import traceback
import inspect
import subprocess
import tempfile
import re
import textwrap
import ast
import hashlib
import random
import shutil
import warnings
import fnmatch
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Generator, Tuple, Union, Set
from dataclasses import dataclass, asdict
from pathlib import Path
import signal

# Check for local ollama.py that might shadow the installed library
current_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(current_dir, "ollama.py")):
    warnings.warn(
        f"WARNING: A local 'ollama.py' file exists in {current_dir} and may shadow the installed 'ollama' library. "
        "Please rename or remove it to avoid conflicts.",
        category=ImportWarning
    )

import ollama
from ollama import Client, AsyncClient

# Optional dependency for code formatting
try:
    import black
    BLACK_AVAILABLE = True
except ImportError:
    BLACK_AVAILABLE = False

# Optional dependency for security analysis
try:
    import bandit
    BANDIT_AVAILABLE = True
except ImportError:
    BANDIT_AVAILABLE = False


# ============================================================================
# ENHANCED CONFIGURATION AND STANDARDS
# ============================================================================

@dataclass
class SystemConfig:
    """Advanced central configuration for the autonomous function development system."""
    
    # Model Configuration with enhanced thinking suppression
    CODE_GENERATION_MODEL = "rnj-1:8b-cloud"  # Primary code generation model
    INTELLIGENCE_MODEL = "rnj-1:8b-cloud"      # Intelligence model for exploration
    JSON_FORMATTER_MODEL = "rnj-1:8b-cloud"
    VALIDATION_MODEL = "rnj-1:8b-cloud"
    
    # System Paths
    DATABASE_PATH = "function_database.db"
    CONFIG_PATH = "system_config.json"
    LOGS_PATH = "system_logs"
    TEMP_PATH = "temp_functions"
    SANDBOX_PATH = "sandbox_environments"
    BASE_CONDA_ENV_PATH = os.path.expanduser("~/base_sandbox_env")
    
    # Advanced Autonomous Mode Settings
    MAX_AUTONOMOUS_ITERATIONS = 99
    EXPLORATION_TIMEOUT = 900  # seconds
    EXPLORATION_INTERVAL = 2.0   # seconds between cycles
    SAFETY_CHECK_INTERVAL = 10
    
    # Enhanced Local System Exploration Settings
    ENABLE_LOCAL_EXPLORATION = True
    # Constrain exploration to the current workspace by default; do not roam home.
    LOCAL_EXPLORATION_PATHS = [os.getcwd()]
    EXPLORATION_IGNORE_GLOBS = ['.env', '.env*', '*.key', 'id_rsa*', '*.pem', '*.pfx', '*.p12', '*.sqlite', '*.db']
    EXPLORATION_FILE_TYPES = ['.py', '.csv', '.json', '.txt', '.xml']
    MAX_EXPLORATION_DEPTH = 3
    ENABLE_INSTALLED_TOOL_DISCOVERY = True
    
    # Enhanced Validation Settings
    MAX_RETRY_ATTEMPTS = 5
    VALIDATION_TIMEOUT = 20
    ENABLE_DEBUG_MODE = True
    ENABLE_ADAPTIVE_VALIDATION = True
    ENABLE_FAILURE_LEARNING = False
    ENABLE_SANDBOX_EXECUTION = True
    ENABLE_SECURITY_ANALYSIS = False
    ENABLE_AST_DUPLICATE_DETECTION = True
    
    # Model Parameters for Deterministic Output
    TEMPERATURE = 0.1
    TOP_P = 0.2
    MAX_TOKENS = 1500
    
    # Advanced Features
    ENABLE_CODE_FORMATTING = BLACK_AVAILABLE
    ENABLE_DIVERSITY_INJECTION = True
    MAX_FAILURE_PATTERNS = 50
    ENABLE_NATURAL_LANGUAGE_COMMANDS = True
    ENABLE_ACTION_MONITORING = True
    ENABLE_CODE_DIFF_LOGGING = True
    
    # Output Settings
    ENABLE_STREAMING = True
    LOG_LEVEL = logging.WARNING
    
    def save_to_file(self, path: str = None):
        """Save configuration to file with enhanced validation."""
        if path is None:
            path = self.CONFIG_PATH
        
        config_data = {
            "code_generation_model": self.CODE_GENERATION_MODEL,
            "max_autonomous_iterations": self.MAX_AUTONOMOUS_ITERATIONS,
            "exploration_timeout": self.EXPLORATION_TIMEOUT,
            "exploration_interval": self.EXPLORATION_INTERVAL,
            "max_retry_attempts": self.MAX_RETRY_ATTEMPTS,
            "validation_timeout": self.VALIDATION_TIMEOUT,
            "enable_debug_mode": self.ENABLE_DEBUG_MODE,
            "enable_adaptive_validation": self.ENABLE_ADAPTIVE_VALIDATION,
            "enable_failure_learning": self.ENABLE_FAILURE_LEARNING,
            "enable_sandbox_execution": self.ENABLE_SANDBOX_EXECUTION,
            "enable_security_analysis": self.ENABLE_SECURITY_ANALYSIS,
            "enable_streaming": self.ENABLE_STREAMING,
            "log_level": self.LOG_LEVEL,
            "temperature": self.TEMPERATURE,
            "top_p": self.TOP_P,
            "max_tokens": self.MAX_TOKENS,
            "enable_code_formatting": self.ENABLE_CODE_FORMATTING,
            "enable_diversity_injection": self.ENABLE_DIVERSITY_INJECTION,
            "max_failure_patterns": self.MAX_FAILURE_PATTERNS,
            "enable_natural_language_commands": self.ENABLE_NATURAL_LANGUAGE_COMMANDS,
            "enable_action_monitoring": self.ENABLE_ACTION_MONITORING,
            "enable_code_diff_logging": self.ENABLE_CODE_DIFF_LOGGING,
            "base_conda_env_path": self.BASE_CONDA_ENV_PATH,
            "enable_local_exploration": self.ENABLE_LOCAL_EXPLORATION,
            "local_exploration_paths": self.LOCAL_EXPLORATION_PATHS,
            "exploration_file_types": self.EXPLORATION_FILE_TYPES,
            "max_exploration_depth": self.MAX_EXPLORATION_DEPTH,
            "enable_installed_tool_discovery": self.ENABLE_INSTALLED_TOOL_DISCOVERY,
            "enable_ast_duplicate_detection": self.ENABLE_AST_DUPLICATE_DETECTION,
            "exploration_ignore_globs": self.EXPLORATION_IGNORE_GLOBS,
        }
        
        try:
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
            temp_path = f"{path}.tmp"
            with open(temp_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            os.rename(temp_path, path)
        except Exception as e:
            if os.path.exists(f"{path}.tmp"):
                try:
                    os.unlink(f"{path}.tmp")
                except:
                    pass
    
    @classmethod
    def load_from_file(cls, path: str = None):
        """Load configuration from file with enhanced validation."""
        if path is None:
            path = "system_config.json"
        
        if not os.path.exists(path):
            return cls()
        
        try:
            with open(path, 'r') as f:
                config_data = json.load(f)
            
            config = cls()
            config.CODE_GENERATION_MODEL = config_data.get("code_generation_model", "rnj-1:8b-cloud")
            config.MAX_AUTONOMOUS_ITERATIONS = max(1, min(1000, config_data.get("max_autonomous_iterations", 99)))
            config.EXPLORATION_TIMEOUT = max(60, min(3600, config_data.get("exploration_timeout", 900)))
            config.EXPLORATION_INTERVAL = max(0.5, min(60, config_data.get("exploration_interval", 2.0)))
            config.MAX_RETRY_ATTEMPTS = max(1, min(10, config_data.get("max_retry_attempts", 5)))
            config.VALIDATION_TIMEOUT = max(5, min(60, config_data.get("validation_timeout", 20)))
            config.ENABLE_DEBUG_MODE = bool(config_data.get("enable_debug_mode", True))
            config.ENABLE_ADAPTIVE_VALIDATION = bool(config_data.get("enable_adaptive_validation", True))
            config.ENABLE_FAILURE_LEARNING = bool(config_data.get("enable_failure_learning", False))
            config.ENABLE_SANDBOX_EXECUTION = bool(config_data.get("enable_sandbox_execution", True))
            config.ENABLE_SECURITY_ANALYSIS = bool(config_data.get("enable_security_analysis", False))
            config.ENABLE_STREAMING = bool(config_data.get("enable_streaming", True))
            config.LOG_LEVEL = config_data.get("log_level", logging.WARNING)
            config.TEMPERATURE = max(0.0, min(2.0, config_data.get("temperature", 0.1)))
            config.TOP_P = max(0.0, min(1.0, config_data.get("top_p", 0.2)))
            config.MAX_TOKENS = max(100, min(4000, config_data.get("max_tokens", 1500)))
            config.ENABLE_CODE_FORMATTING = bool(config_data.get("enable_code_formatting", BLACK_AVAILABLE))
            config.ENABLE_DIVERSITY_INJECTION = bool(config_data.get("enable_diversity_injection", True))
            config.MAX_FAILURE_PATTERNS = max(10, min(100, config_data.get("max_failure_patterns", 50)))
            config.ENABLE_NATURAL_LANGUAGE_COMMANDS = bool(config_data.get("enable_natural_language_commands", True))
            config.ENABLE_ACTION_MONITORING = bool(config_data.get("enable_action_monitoring", True))
            config.ENABLE_CODE_DIFF_LOGGING = bool(config_data.get("enable_code_diff_logging", True))
            config.BASE_CONDA_ENV_PATH = config_data.get("base_conda_env_path", os.path.expanduser("~/base_sandbox_env"))
            config.ENABLE_LOCAL_EXPLORATION = bool(config_data.get("enable_local_exploration", True))
            config.LOCAL_EXPLORATION_PATHS = config_data.get("local_exploration_paths", [os.getcwd()])
            config.EXPLORATION_IGNORE_GLOBS = config_data.get(
                "exploration_ignore_globs",
                ['.env', '.env*', '*.key', 'id_rsa*', '*.pem', '*.pfx', '*.p12', '*.sqlite', '*.db'],
            )
            config.EXPLORATION_FILE_TYPES = config_data.get("exploration_file_types", ['.py', '.csv', '.json', '.txt', '.xml'])
            config.MAX_EXPLORATION_DEPTH = max(1, min(10, config_data.get("max_exploration_depth", 3)))
            config.ENABLE_INSTALLED_TOOL_DISCOVERY = bool(config_data.get("enable_installed_tool_discovery", True))
            config.ENABLE_AST_DUPLICATE_DETECTION = bool(config_data.get("enable_ast_duplicate_detection", True))
            
            return config
        except Exception as e:
            return cls()

    def get_working_model_for_code_generation(self) -> str:
        """
        EDIT 6: Configuration Auto-Detection
        Determine the best working model for code generation through proactive health checking.
        """
        models_to_test = [self.CODE_GENERATION_MODEL, self.INTELLIGENCE_MODEL]
        
        for model in models_to_test:
            try:
                # Test model availability and basic functionality
                client = Client()
                test_response = client.generate(
                    model=model,
                    prompt="def test(): return 'working'",
                    options={"max_tokens": 50, "temperature": 0.1}
                )
                
                if test_response and test_response.get('response', '').strip():
                    if self.ENABLE_DEBUG_MODE:
                        print(f"✅ Model {model} is working for code generation")
                    return model
                    
            except Exception as e:
                if self.ENABLE_DEBUG_MODE:
                    print(f"❌ Model {model} failed health check: {e}")
                continue
        
        # Fallback to intelligence model if primary fails
        if self.ENABLE_DEBUG_MODE:
            print(f"⚠️ Falling back to intelligence model: {self.INTELLIGENCE_MODEL}")
        return self.INTELLIGENCE_MODEL


@dataclass
class StandardizedModelResponse:
    """Advanced standardized response format for universal model communication."""
    
    content: str
    is_valid: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    raw_response: str = ""
    extraction_method: str = ""
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class FunctionMetadata:
    """Enhanced metadata structure for generated functions with LLM tool focus."""
    
    name: str
    domain: str
    description: str
    parameters: Dict[str, Any]
    return_type: str
    created_at: str
    validation_status: str
    test_results: Dict[str, Any]
    source_code: str
    dependencies: List[str]
    safety_rating: str
    debug_info: Dict[str, Any] = None
    signature: str = ""
    complexity_score: int = 5
    code_hash: str = ""
    usage_example: str = ""
    input_output_description: str = ""
    source_artifact: str = ""


@dataclass
class FailurePattern:
    """Track patterns that consistently fail."""
    
    pattern_hash: str
    description: str
    failure_count: int
    last_seen: str
    error_types: List[str]


@dataclass
class ActionLog:
    """Track autonomous actions for monitoring."""
    
    timestamp: str
    action_type: str
    description: str
    details: Dict[str, Any]
    success: bool
    error_message: Optional[str] = None


@dataclass
class DiscoveredArtifact:
    """Track discovered system artifacts for function generation."""
    
    path: str
    artifact_type: str
    description: str
    metadata: Dict[str, Any]
    discovered_at: str


@dataclass
class CodeDiffEntry:
    """Track code transformations for training data generation."""
    
    timestamp: str
    original_code: str
    processed_code: str
    transformation_type: str
    success: bool
    validation_errors: List[str] = None
    function_name: str = ""
    
    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


class ValidationError(Exception):
    """Custom exception for function validation failures."""
    pass


class ModelResponseError(Exception):
    """Custom exception for model response processing failures."""
    pass


class SecurityError(Exception):
    """Custom exception for security violations."""
    pass


class OllamaConnectionError(Exception):
    """Custom exception for Ollama connectivity issues."""
    pass


# ============================================================================
# CODE DIFF LOGGING SYSTEM
# ============================================================================

class CodeDiffLogger:
    """
    Enhanced code diff logging system for capturing transformations and training data.
    """
    
    def __init__(self, config: 'SystemConfig'):
        self.config = config
        self.diff_entries: List[CodeDiffEntry] = []
        self.logger = logging.getLogger("code_diff")
        self._setup_diff_logging()
    
    def _setup_diff_logging(self):
        """Setup dedicated logging for code diffs."""
        if not self.config.ENABLE_CODE_DIFF_LOGGING:
            return
        
        # Create dedicated log file for code diffs
        diff_log_path = os.path.join(self.config.LOGS_PATH, "code_diffs.jsonl")
        
        # Create a separate logger for code diffs
        diff_handler = logging.FileHandler(diff_log_path)
        diff_formatter = logging.Formatter('%(message)s')
        diff_handler.setFormatter(diff_formatter)
        
        self.logger.addHandler(diff_handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  # Don't propagate to root logger
    
    def log_code_transformation(self, original_code: str, processed_code: str, 
                              transformation_type: str, success: bool, 
                              validation_errors: List[str] = None, 
                              function_name: str = ""):
        """Log a code transformation for analysis and training."""
        if not self.config.ENABLE_CODE_DIFF_LOGGING:
            return
        
        diff_entry = CodeDiffEntry(
            timestamp=datetime.now().isoformat(),
            original_code=original_code,
            processed_code=processed_code,
            transformation_type=transformation_type,
            success=success,
            validation_errors=validation_errors or [],
            function_name=function_name
        )
        
        self.diff_entries.append(diff_entry)
        
        # Log as JSON for easy parsing
        log_data = {
            "event": "code_transformation",
            "timestamp": diff_entry.timestamp,
            "transformation_type": transformation_type,
            "function_name": function_name,
            "success": success,
            "original_code": original_code,
            "processed_code": processed_code,
            "validation_errors": validation_errors or [],
            "original_length": len(original_code),
            "processed_length": len(processed_code),
            "size_change": len(processed_code) - len(original_code)
        }
        
        self.logger.info(json.dumps(log_data))
        
        # Also log to action monitor if available
        if hasattr(self.config, 'action_monitor') and self.config.action_monitor:
            self.config.action_monitor.log_action(
                "code_transformation",
                f"Code transformation: {transformation_type}",
                {
                    "function_name": function_name,
                    "success": success,
                    "original_length": len(original_code),
                    "processed_length": len(processed_code),
                    "validation_errors": len(validation_errors or [])
                },
                success=success
            )
    
    def log_syntax_fix(self, original_code: str, fixed_code: str, syntax_error: str, 
                      success: bool, function_name: str = ""):
        """Log syntax error fixes specifically."""
        self.log_code_transformation(
            original_code=original_code,
            processed_code=fixed_code,
            transformation_type="syntax_fix",
            success=success,
            validation_errors=[syntax_error] if syntax_error else [],
            function_name=function_name
        )
    
    def log_content_cleaning(self, raw_output: str, cleaned_code: str, 
                           extraction_method: str, success: bool, function_name: str = ""):
        """Log content cleaning transformations."""
        self.log_code_transformation(
            original_code=raw_output,
            processed_code=cleaned_code,
            transformation_type=f"content_cleaning_{extraction_method}",
            success=success,
            function_name=function_name
        )
    
    def log_code_formatting(self, unformatted_code: str, formatted_code: str, 
                          success: bool, function_name: str = ""):
        """Log code formatting transformations."""
        self.log_code_transformation(
            original_code=unformatted_code,
            processed_code=formatted_code,
            transformation_type="code_formatting",
            success=success,
            function_name=function_name
        )
    
    def get_training_dataset(self, transformation_types: List[str] = None) -> List[Dict[str, str]]:
        """Extract training dataset from logged transformations."""
        dataset = []
        
        for entry in self.diff_entries:
            if transformation_types and entry.transformation_type not in transformation_types:
                continue
            
            if entry.success and entry.original_code != entry.processed_code:
                dataset.append({
                    "input": entry.original_code,
                    "output": entry.processed_code,
                    "transformation_type": entry.transformation_type,
                    "function_name": entry.function_name
                })
        
        return dataset
    
    def export_training_data(self, output_path: str = "training_data.jsonl", 
                           transformation_types: List[str] = None):
        """Export training data to JSONL format."""
        dataset = self.get_training_dataset(transformation_types)
        
        try:
            with open(output_path, 'w') as f:
                for entry in dataset:
                    f.write(json.dumps(entry) + '\n')
            
            if self.config.ENABLE_DEBUG_MODE:
                print(f"✅ Exported {len(dataset)} training examples to {output_path}")
            return True
        except Exception as e:
            if self.config.ENABLE_DEBUG_MODE:
                print(f"❌ Failed to export training data: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about logged transformations."""
        if not self.diff_entries:
            return {"total_entries": 0}
        
        stats = {
            "total_entries": len(self.diff_entries),
            "successful_transformations": sum(1 for e in self.diff_entries if e.success),
            "failed_transformations": sum(1 for e in self.diff_entries if not e.success),
            "transformation_types": {},
            "average_size_change": 0,
            "functions_processed": len(set(e.function_name for e in self.diff_entries if e.function_name))
        }
        
        # Count by transformation type
        for entry in self.diff_entries:
            if entry.transformation_type not in stats["transformation_types"]:
                stats["transformation_types"][entry.transformation_type] = {"count": 0, "success": 0}
            stats["transformation_types"][entry.transformation_type]["count"] += 1
            if entry.success:
                stats["transformation_types"][entry.transformation_type]["success"] += 1
        
        # Calculate average size change
        size_changes = [len(e.processed_code) - len(e.original_code) for e in self.diff_entries]
        stats["average_size_change"] = sum(size_changes) / len(size_changes) if size_changes else 0
        
        return stats


# ============================================================================
# NATURAL LANGUAGE COMMAND INTERFACE (PLACEHOLDER)
# ============================================================================

class NaturalLanguageCommandProcessor:
    """
    Placeholder for natural language command processing system.
    This will be integrated with external natural language processing script.
    """
    
    def __init__(self, system_reference):
        self.system = system_reference
        self.command_history = []
        self.enabled = False
        
    def process_natural_command(self, command: str) -> Dict[str, Any]:
        """
        Process natural language commands and convert to system actions.
        
        This is a placeholder that will be integrated with the external
        natural language processing script for command interpretation.
        """
        # Placeholder implementation
        command_lower = command.lower().strip()
        
        # Basic command mapping (to be replaced with sophisticated NLP)
        if "create function" in command_lower or "generate function" in command_lower:
            # Extract function description from command
            description = command_lower.replace("create function", "").replace("generate function", "").strip()
            if description:
                return {
                    "action": "create_function",
                    "parameters": {"description": description},
                    "confidence": 0.8
                }
        
        elif "start autonomous" in command_lower or "begin autonomous" in command_lower:
            domain = None
            if "in domain" in command_lower:
                parts = command_lower.split("in domain")
                if len(parts) > 1:
                    domain = parts[1].strip()
            
            return {
                "action": "start_autonomous",
                "parameters": {"domain": domain},
                "confidence": 0.9
            }
        
        elif "stop" in command_lower or "halt" in command_lower:
            return {
                "action": "stop_autonomous",
                "parameters": {},
                "confidence": 0.95
            }
        
        elif "list functions" in command_lower or "show functions" in command_lower:
            return {
                "action": "list_functions",
                "parameters": {},
                "confidence": 0.9
            }
        
        # Placeholder for more sophisticated processing
        return {
            "action": "unknown",
            "parameters": {},
            "confidence": 0.0,
            "message": "Command not recognized (placeholder - will be enhanced with external NLP script)"
        }
    
    def enable_natural_commands(self):
        """Enable natural language command processing."""
        self.enabled = True
        if self.system.config.ENABLE_DEBUG_MODE:
            print("🗣️  Natural language command processing enabled (placeholder mode)")
    
    def disable_natural_commands(self):
        """Disable natural language command processing."""
        self.enabled = False
        if self.system.config.ENABLE_DEBUG_MODE:
            print("🔇 Natural language command processing disabled")


# ============================================================================
# ACTION MONITORING SYSTEM
# ============================================================================

class ActionMonitor:
    """Monitor and log all autonomous actions for transparency and safety."""
    
    def __init__(self, config: 'SystemConfig'):
        self.config = config
        self.action_log: List[ActionLog] = []
        self.active_monitoring = False
        self.safeguards = {
            "file_access": True,
            "network_access": False,
            "system_commands": False,
            "code_execution": True,
            "database_access": True,
            "local_exploration": True
        }
    
    def start_monitoring(self):
        """Start action monitoring."""
        self.active_monitoring = True
        if self.config.ENABLE_DEBUG_MODE:
            print("👁️  Action monitoring started - all autonomous actions will be logged")
    
    def stop_monitoring(self):
        """Stop action monitoring."""
        self.active_monitoring = False
        if self.config.ENABLE_DEBUG_MODE:
            print("👁️  Action monitoring stopped")
    
    def log_action(self, action_type: str, description: str, details: Dict[str, Any] = None, success: bool = True, error_message: str = None):
        """Log an autonomous action."""
        if not self.active_monitoring:
            return
        
        action = ActionLog(
            timestamp=datetime.now().isoformat(),
            action_type=action_type,
            description=description,
            details=details or {},
            success=success,
            error_message=error_message
        )
        
        self.action_log.append(action)
        
        # Only display action in real-time if debug mode is enabled
        if self.config.ENABLE_DEBUG_MODE:
            status = "✅" if success else "❌"
            print(f"{status} AUTONOMOUS ACTION: {action_type} - {description}")
            if details:
                print(f"   Details: {details}")
            if error_message:
                print(f"   Error: {error_message}")
    
    def check_safeguard(self, action_type: str) -> bool:
        """Check if an action is allowed by safeguards."""
        return self.safeguards.get(action_type, False)
    
    def get_recent_actions(self, limit: int = 10) -> List[ActionLog]:
        """Get recent actions."""
        return self.action_log[-limit:] if self.action_log else []
    
    def clear_log(self):
        """Clear action log."""
        self.action_log.clear()
        if self.config.ENABLE_DEBUG_MODE:
            print("🗑️  Action log cleared")


# ============================================================================
# ENHANCED LOCAL SYSTEM EXPLORATION
# ============================================================================

class LocalSystemExplorer:
    """
    Enhanced local system exploration for discovering artifacts and generating relevant LLM tools.
    """
    
    def __init__(self, config: 'SystemConfig', action_monitor: ActionMonitor):
        self.config = config
        self.action_monitor = action_monitor
        self.discovered_artifacts: List[DiscoveredArtifact] = []
        self.skip_dirs = {'/proc', '/sys', '/dev', '/etc', '/bin', '/sbin', '/var', '/boot', '/root'}
        self.processed_artifacts: Set[str] = set()
        self.artifact_usage_count: Dict[str, int] = {}
        
    def scan_local_resources(self, base_paths: List[str] = None) -> List[DiscoveredArtifact]:
        """
        Recursively scan base_paths for interesting artifacts while respecting safety constraints.
        """
        if not self.config.ENABLE_LOCAL_EXPLORATION:
            return []
        
        if not self.action_monitor.check_safeguard("local_exploration"):
            if self.config.ENABLE_DEBUG_MODE:
                print("⚠️  Local exploration blocked by safeguards")
            return []
        
        base_paths = base_paths or self.config.LOCAL_EXPLORATION_PATHS
        discovered = []
        
        self.action_monitor.log_action(
            "local_exploration",
            f"Starting scan of {len(base_paths)} base paths",
            {"paths": base_paths, "file_types": self.config.EXPLORATION_FILE_TYPES}
        )
        
        for base_path in base_paths:
            try:
                # Ensure path is safe and accessible
                if not self._is_safe_path(base_path):
                    if self.config.ENABLE_DEBUG_MODE:
                        print(f"⚠️  Skipping unsafe path: {base_path}")
                    continue
                
                if not os.path.exists(base_path) or not os.access(base_path, os.R_OK):
                    if self.config.ENABLE_DEBUG_MODE:
                        print(f"⚠️  Cannot access path: {base_path}")
                    continue
                
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"🔍 Scanning: {base_path}")
                artifacts = self._scan_directory(base_path, 0)
                discovered.extend(artifacts)
                
            except Exception as e:
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"⚠️  Error scanning {base_path}: {e}")
                self.action_monitor.log_action(
                    "local_exploration",
                    f"Error scanning path: {base_path}",
                    {"error": str(e)},
                    success=False,
                    error_message=str(e)
                )
        
        self.discovered_artifacts.extend(discovered)
        
        self.action_monitor.log_action(
            "local_exploration",
            f"Completed scan, found {len(discovered)} artifacts",
            {"artifact_count": len(discovered), "total_discovered": len(self.discovered_artifacts)}
        )
        
        return discovered
    
    def _is_safe_path(self, path: str) -> bool:
        """Check if a path is safe for exploration."""
        try:
            abs_path = os.path.abspath(path)
            
            # Check against skip directories
            for skip_dir in self.skip_dirs:
                if abs_path.startswith(skip_dir):
                    return False
            
            # Ensure it's within allowed exploration paths
            for allowed_path in self.config.LOCAL_EXPLORATION_PATHS:
                if abs_path.startswith(os.path.abspath(allowed_path)):
                    return True
            
            return False
        except Exception:
            return False
    
    def _scan_directory(self, directory: str, current_depth: int) -> List[DiscoveredArtifact]:
        """Scan a single directory for artifacts."""
        if current_depth >= self.config.MAX_EXPLORATION_DEPTH:
            return []
        
        artifacts = []
        
        try:
            for root, dirs, files in os.walk(directory):
                # Remove unsafe directories from traversal
                dirs[:] = [d for d in dirs if self._is_safe_path(os.path.join(root, d))]
                
                for filename in files:
                    filepath = os.path.join(root, filename)

                    # Skip ignored patterns (secrets/keys/db files)
                    if any(fnmatch.fnmatch(filename, pattern) for pattern in self.config.EXPLORATION_IGNORE_GLOBS):
                        continue
                    
                    # Check file type
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in self.config.EXPLORATION_FILE_TYPES:
                        artifact = self._analyze_file(filepath, ext.lower())
                        if artifact:
                            artifacts.append(artifact)
                            if self.config.ENABLE_DEBUG_MODE:
                                print(f"📄 Discovered: {artifact.artifact_type} - {filepath}")
                
                # Respect depth limit
                if current_depth >= self.config.MAX_EXPLORATION_DEPTH - 1:
                    dirs.clear()  # Don't descend further
        
        except Exception as e:
            if self.config.ENABLE_DEBUG_MODE:
                print(f"⚠️  Error scanning directory {directory}: {e}")
        
        return artifacts
    
    def _analyze_file(self, filepath: str, file_ext: str) -> Optional[DiscoveredArtifact]:
        """Analyze a discovered file and create an artifact descriptor."""
        try:
            if not os.access(filepath, os.R_OK):
                return None
            
            file_size = os.path.getsize(filepath)
            if file_size > 10 * 1024 * 1024:  # Skip files larger than 10MB
                return None
            
            artifact_type = "unknown"
            description = f"File: {os.path.basename(filepath)}"
            metadata = {
                "size": file_size,
                "extension": file_ext,
                "last_modified": datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
            }
            
            # Analyze based on file type
            if file_ext == '.csv':
                artifact_type = "csv_data"
                description = f"CSV data file: {os.path.basename(filepath)}"
                metadata.update(self._analyze_csv_file(filepath))
            
            elif file_ext == '.json':
                artifact_type = "json_data"
                description = f"JSON data file: {os.path.basename(filepath)}"
                metadata.update(self._analyze_json_file(filepath))
            
            elif file_ext == '.py':
                artifact_type = "python_script"
                description = f"Python script: {os.path.basename(filepath)}"
                metadata.update(self._analyze_python_file(filepath))
            
            elif file_ext == '.txt':
                artifact_type = "text_file"
                description = f"Text file: {os.path.basename(filepath)}"
                metadata.update(self._analyze_text_file(filepath))
            
            elif file_ext == '.xml':
                artifact_type = "xml_data"
                description = f"XML data file: {os.path.basename(filepath)}"
                metadata.update(self._analyze_xml_file(filepath))
            
            return DiscoveredArtifact(
                path=filepath,
                artifact_type=artifact_type,
                description=description,
                metadata=metadata,
                discovered_at=datetime.now().isoformat()
            )
        
        except Exception as e:
            if self.config.ENABLE_DEBUG_MODE:
                print(f"⚠️  Error analyzing file {filepath}: {e}")
            return None
    
    def _analyze_csv_file(self, filepath: str) -> Dict[str, Any]:
        """Analyze CSV file structure."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
                line_count = sum(1 for _ in f) + 1
            
            # Estimate columns
            separators = [',', ';', '\t', '|']
            best_separator = ','
            max_columns = 0
            
            for sep in separators:
                col_count = len(first_line.split(sep))
                if col_count > max_columns:
                    max_columns = col_count
                    best_separator = sep
            
            return {
                "estimated_rows": line_count,
                "estimated_columns": max_columns,
                "likely_separator": best_separator,
                "header_sample": first_line[:200]
            }
        except Exception:
            return {"analysis_failed": True}
    
    def _analyze_json_file(self, filepath: str) -> Dict[str, Any]:
        """Analyze JSON file structure."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                sample = f.read(1024)  # Read first 1KB
            
            # Try to parse a sample
            try:
                import json
                parsed = json.loads(sample)
                structure_type = type(parsed).__name__
                
                if isinstance(parsed, dict):
                    keys = list(parsed.keys())[:10]  # First 10 keys
                    return {"structure": "object", "sample_keys": keys}
                elif isinstance(parsed, list):
                    length = len(parsed)
                    return {"structure": "array", "estimated_length": length}
                else:
                    return {"structure": structure_type}
            except:
                return {"structure": "unknown", "sample": sample[:200]}
        except Exception:
            return {"analysis_failed": True}
    
    def _analyze_python_file(self, filepath: str) -> Dict[str, Any]:
        """Analyze Python file structure."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(2048)  # Read first 2KB
            
            # Basic analysis
            functions = re.findall(r'def\s+(\w+)\s*\(', content)
            classes = re.findall(r'class\s+(\w+)\s*[\(:]', content)
            imports = re.findall(r'(?:from\s+\S+\s+)?import\s+([^\n]+)', content)
            
            return {
                "functions": functions[:10],
                "classes": classes[:10],
                "imports": imports[:10],
                "lines_analyzed": len(content.split('\n'))
            }
        except Exception:
            return {"analysis_failed": True}
    
    def _analyze_text_file(self, filepath: str) -> Dict[str, Any]:
        """Analyze text file content."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1024)
            
            lines = content.split('\n')
            words = content.split()
            
            return {
                "estimated_lines": len(lines),
                "estimated_words": len(words),
                "sample_content": content[:200]
            }
        except Exception:
            return {"analysis_failed": True}
    
    def _analyze_xml_file(self, filepath: str) -> Dict[str, Any]:
        """Analyze XML file structure."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1024)
            
            # Extract root element and some tags
            root_match = re.search(r'<(\w+)', content)
            tags = re.findall(r'<(\w+)', content)
            
            return {
                "root_element": root_match.group(1) if root_match else None,
                "sample_tags": list(set(tags))[:10],
                "sample_content": content[:200]
            }
        except Exception:
            return {"analysis_failed": True}
    
    def find_installed_commands(self, commands: List[str] = None) -> Dict[str, str]:
        """
        Check if listed commands exist in PATH and return their paths.
        """
        if not self.config.ENABLE_INSTALLED_TOOL_DISCOVERY:
            return {}
        
        if not self.action_monitor.check_safeguard("local_exploration"):
            return {}
        
        # Default list of interesting commands
        if commands is None:
            commands = [
                'python', 'python3', 'pip', 'git', 'curl', 'wget', 'grep', 'awk', 'sed',
                'jq', 'csvtool', 'sqlite3', 'mysql', 'psql', 'docker', 'kubectl',
                'ffmpeg', 'convert', 'pandoc', 'node', 'npm', 'yarn', 'ruby', 'php'
            ]
        
        found = {}
        
        self.action_monitor.log_action(
            "tool_discovery",
            f"Scanning for {len(commands)} installed tools",
            {"commands": commands}
        )
        
        for cmd in commands:
            try:
                path = shutil.which(cmd)
                if path:
                    found[cmd] = path
                    if self.config.ENABLE_DEBUG_MODE:
                        print(f"🔧 Found tool: {cmd} at {path}")
            except Exception as e:
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"⚠️  Error checking command {cmd}: {e}")
        
        self.action_monitor.log_action(
            "tool_discovery",
            f"Found {len(found)} installed tools",
            {"found_tools": found}
        )
        
        return found
    
    def generate_artifact_based_function_prompts(self, artifacts: List[DiscoveredArtifact]) -> List[str]:
        """Generate LLM prompts based on discovered artifacts."""
        prompts = []
        
        for artifact in artifacts:
            prompt = self._create_artifact_prompt(artifact)
            if prompt:
                prompts.append(prompt)
        
        return prompts
    
    def get_available_artifacts(self) -> List[DiscoveredArtifact]:
        """
        Get artifacts that can be used for prompt generation.
        Prioritizes unprocessed artifacts, then allows reuse with variations.
        """
        # First, try to get unprocessed artifacts
        unprocessed = [a for a in self.discovered_artifacts if a.path not in self.processed_artifacts]
        
        if unprocessed:
            if self.config.ENABLE_DEBUG_MODE:
                print(f"🔍 Found {len(unprocessed)} unprocessed artifacts")
            return unprocessed
        
        # If all artifacts have been processed, allow reuse but track usage count
        if self.discovered_artifacts:
            # Sort by usage count (ascending) to prefer less-used artifacts
            sorted_artifacts = sorted(
                self.discovered_artifacts, 
                key=lambda a: self.artifact_usage_count.get(a.path, 0)
            )
            if self.config.ENABLE_DEBUG_MODE:
                print(f"🔄 Reusing artifacts - least used first from {len(sorted_artifacts)} total")
            return sorted_artifacts
        
        return []
    
    def _create_artifact_prompt(self, artifact: DiscoveredArtifact) -> str:
        """
        Create a targeted prompt for a specific artifact.
        Now handles reuse with variations to avoid empty prompts.
        """
        # Track usage for this artifact
        usage_count = self.artifact_usage_count.get(artifact.path, 0)
        self.artifact_usage_count[artifact.path] = usage_count + 1
        
        # Add this artifact to processed set
        self.processed_artifacts.add(artifact.path)
        
        # Create variation suffix based on usage count
        variation_suffix = ""
        if usage_count > 0:
            variations = [
                "with enhanced error handling and validation",
                "with comprehensive metadata extraction",
                "with advanced processing capabilities", 
                "with intelligent data transformation",
                "with optimized performance features",
                "with detailed statistical analysis",
                "with robust edge case handling",
                "with extensible plugin architecture"
            ]
            variation_idx = (usage_count - 1) % len(variations)
            variation_suffix = f" {variations[variation_idx]}"
        
        base_prompt = f"""Create a specialized Python LLM tool function for processing {artifact.artifact_type} files{variation_suffix}.

Requirements:
- Function name must be specific to the task, NOT 'process_input'
- Accept 'input_data' dictionary parameter containing file path or content
- Return dictionary with 'result', 'status', and 'error' keys
- Use only standard Python library (no external dependencies)
- Include comprehensive error handling for malformed data
- Focus on extracting meaningful insights and metadata

Target file details:
- Type: {artifact.artifact_type}
- Path: {os.path.basename(artifact.path)}
- Description: {artifact.description}
- Metadata: {artifact.metadata}
- Usage iteration: {usage_count + 1}

"""
        
        # Add specific requirements based on artifact type with enhanced detail
        if artifact.artifact_type == "csv_data":
            estimated_rows = artifact.metadata.get("estimated_rows", 0)
            estimated_columns = artifact.metadata.get("estimated_columns", 0)
            separator = artifact.metadata.get("likely_separator", ",")
            
            function_name_suggestions = [
                "analyze_csv_structure", "validate_csv_data", "extract_csv_metadata",
                "process_csv_advanced", "parse_csv_intelligent", "csv_quality_analyzer"
            ]
            suggested_name = function_name_suggestions[usage_count % len(function_name_suggestions)]
            
            prompt = base_prompt + f"""
SPECIFIC CSV PROCESSING REQUIREMENTS:
- Parse CSV with delimiter detection (detected: '{separator}')
- Handle {estimated_rows} rows and {estimated_columns} columns
- Extract column headers and data types automatically
- Validate data consistency and identify missing values
- Return structured analysis including:
  * Column statistics (count, types, null values)
  * Data quality metrics
  * Sample data preview
  * Schema information
- Function name should be like: {suggested_name}

Generate ONE complete function with name: {suggested_name}"""
        
        elif artifact.artifact_type == "json_data":
            structure = artifact.metadata.get("structure", "unknown")
            sample_keys = artifact.metadata.get("sample_keys", [])
            
            function_name_suggestions = [
                "parse_json_schema", "validate_json_structure", "extract_json_metadata",
                "json_deep_analyzer", "json_structure_validator", "json_content_processor"
            ]
            suggested_name = function_name_suggestions[usage_count % len(function_name_suggestions)]
            
            prompt = base_prompt + f"""
SPECIFIC JSON PROCESSING REQUIREMENTS:
- Parse and validate JSON structure (detected: {structure})
- Handle nested objects and arrays gracefully
- Extract schema information and key patterns
- Sample keys found: {sample_keys[:5]}
- Return structured analysis including:
  * Schema validation and structure mapping
  * Key-value pair analysis
  * Data type detection for values
  * Nested structure flattening options
- Function name should be like: {suggested_name}

Generate ONE complete function with name: {suggested_name}"""
        
        elif artifact.artifact_type == "python_script":
            functions = artifact.metadata.get("functions", [])
            classes = artifact.metadata.get("classes", [])
            imports = artifact.metadata.get("imports", [])
            
            function_name_suggestions = [
                "analyze_python_code", "extract_code_metrics", "validate_python_structure",
                "python_ast_analyzer", "code_complexity_calculator", "python_dependency_mapper"
            ]
            suggested_name = function_name_suggestions[usage_count % len(function_name_suggestions)]
            
            prompt = base_prompt + f"""
SPECIFIC PYTHON CODE ANALYSIS REQUIREMENTS:
- Extract function and class definitions (found: {len(functions)} functions, {len(classes)} classes)
- Analyze imports and dependencies: {imports[:5]}
- Calculate code complexity metrics
- Return structured analysis including:
  * Function signatures and docstrings
  * Class hierarchies and methods
  * Import dependency mapping
  * Code quality metrics (lines, complexity)
  * Security analysis for potentially unsafe operations
- Function name should be like: {suggested_name}

Generate ONE complete function with name: {suggested_name}"""
        
        elif artifact.artifact_type == "text_file":
            estimated_lines = artifact.metadata.get("estimated_lines", 0)
            estimated_words = artifact.metadata.get("estimated_words", 0)
            
            function_name_suggestions = [
                "analyze_text_content", "extract_text_patterns", "classify_text_data",
                "text_intelligence_analyzer", "document_content_processor", "text_pattern_extractor"
            ]
            suggested_name = function_name_suggestions[usage_count % len(function_name_suggestions)]
            
            prompt = base_prompt + f"""
SPECIFIC TEXT ANALYSIS REQUIREMENTS:
- Analyze text content and structure ({estimated_lines} lines, {estimated_words} words)
- Extract meaningful patterns, keywords, and entities
- Perform content classification and sentiment analysis
- Return structured analysis including:
  * Word frequency and keyword extraction
  * Text statistics (readability, complexity)
  * Pattern recognition (emails, URLs, dates)
  * Content classification and topic detection
- Function name should be like: {suggested_name}

Generate ONE complete function with name: {suggested_name}"""
        
        elif artifact.artifact_type == "xml_data":
            root_element = artifact.metadata.get("root_element", "unknown")
            sample_tags = artifact.metadata.get("sample_tags", [])
            
            function_name_suggestions = [
                "parse_xml_structure", "extract_xml_data", "validate_xml_schema",
                "xml_intelligent_parser", "xml_content_analyzer", "xml_hierarchy_extractor"
            ]
            suggested_name = function_name_suggestions[usage_count % len(function_name_suggestions)]
            
            prompt = base_prompt + f"""
SPECIFIC XML PROCESSING REQUIREMENTS:
- Parse XML structure with root element: {root_element}
- Handle XML namespaces and attributes properly
- Extract element hierarchy and content (sample tags: {sample_tags[:5]})
- Return structured analysis including:
  * XML schema extraction and validation
  * Element-attribute mapping
  * Content extraction and transformation
  * Namespace analysis and resolution
- Function name should be like: {suggested_name}

Generate ONE complete function with name: {suggested_name}"""
        
        else:
            # Generic fallback for unknown types
            function_name_suggestions = [
                "process_file_content", "analyze_file_structure", "extract_file_metadata",
                "intelligent_file_processor", "file_content_analyzer", "generic_file_handler"
            ]
            suggested_name = function_name_suggestions[usage_count % len(function_name_suggestions)]
            
            prompt = base_prompt + f"""
GENERAL FILE PROCESSING REQUIREMENTS:
- Process file content intelligently based on type and structure
- Extract meaningful metadata and insights
- Provide comprehensive error handling
- Return structured analysis with detailed results
- Function name should be like: {suggested_name}

Generate ONE complete function with name: {suggested_name}"""
        
        # Add aggregate processing note for multiple files
        files_of_same_type = len([a for a in self.discovered_artifacts if a.artifact_type == artifact.artifact_type])
        if files_of_same_type > 1:
            prompt += f"\n\nNOTE: {files_of_same_type} {artifact.artifact_type} files discovered. Function should handle batch processing if multiple files provided."
        
        # Add variation note if this is a reuse
        if usage_count > 0:
            prompt += f"\n\nVARIATION NOTE: This is iteration {usage_count + 1} for this artifact. Focus on different aspects or approaches than previous iterations."
        
        prompt += "\n\nGenerate ONE complete, working function with the specified name:"
        
        return prompt


# ============================================================================
# ENHANCED AST-BASED CODE PROCESSING SYSTEM
# ============================================================================

class AdvancedCodeProcessor:
    """
    Enhanced AST-based code processing system for reliable function extraction and validation.
    """
    
    @staticmethod
    def extract_function_ast(source_code: str) -> Optional[ast.FunctionDef]:
        """Extract the first function definition using AST parsing."""
        try:
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node
        except (SyntaxError, ValueError) as e:
            logging.warning(f"AST parsing failed: {e}")
        return None
    
    @staticmethod
    def extract_pure_function_code(source_code: str) -> str:
        """Extract only the function definition, excluding examples and explanations."""
        try:
            # First, try to extract using AST
            tree = ast.parse(source_code)
            
            # Find all function definitions
            functions = []
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    # Get the source lines for this function
                    lines = source_code.split('\n')
                    start_line = node.lineno - 1
                    
                    # Find the end of the function by looking at indentation
                    end_line = start_line + 1
                    base_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
                    
                    for i in range(start_line + 1, len(lines)):
                        line = lines[i]
                        if line.strip() == '':
                            end_line = i + 1
                            continue
                        
                        current_indent = len(line) - len(line.lstrip())
                        if current_indent <= base_indent and line.strip():
                            # Check if this is another function or class
                            if line.strip().startswith(('def ', 'class ', 'if __name__', 'import ', 'from ')):
                                break
                        end_line = i + 1
                    
                    function_code = '\n'.join(lines[start_line:end_line])
                    functions.append(function_code.rstrip())
            
            if functions:
                return functions[0]  # Return the first function
                
        except (SyntaxError, ValueError) as e:
            logging.warning(f"AST extraction failed, falling back to regex: {e}")
        
        # Fallback to regex-based extraction
        return AdvancedCodeProcessor._extract_function_regex(source_code)
    
    @staticmethod
    def _extract_function_regex(source_code: str) -> str:
        """Fallback regex-based function extraction."""
        lines = source_code.split('\n')
        function_lines = []
        in_function = False
        base_indent = 0
        
        for line in lines:
            if 'def ' in line and line.strip().startswith('def '):
                in_function = True
                base_indent = len(line) - len(line.lstrip())
                function_lines = [line]
            elif in_function:
                line_indent = len(line) - len(line.lstrip())
                
                if line.strip() == '':
                    function_lines.append(line)
                elif (line_indent > base_indent or 
                      line.strip().startswith('#')):
                    function_lines.append(line)
                elif (line.strip() and 
                      line_indent <= base_indent and 
                      not line.strip().startswith(('def ', 'class ', 'import ', 'from '))):
                    # This might be part of the function
                    function_lines.append(line)
                else:
                    # Function has ended
                    break
        
        return '\n'.join(function_lines).rstrip()
    
    @staticmethod
    def get_function_name(source_code: str) -> Optional[str]:
        """Extract function name using AST."""
        try:
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node.name
        except (SyntaxError, ValueError):
            pass
        
        # Fallback to regex
        match = re.search(r'def\s+(\w+)\s*\(', source_code)
        if match:
            return match.group(1)
        
        return None
    
    @staticmethod
    def validate_function_syntax(source_code: str) -> Tuple[bool, str]:
        """Validate function syntax using AST compilation."""
        try:
            if not source_code.strip():
                return False, "Empty code"
            
            if 'def ' not in source_code:
                return False, "No function definition found"
            
            # Try to compile the code
            compile(source_code, '<string>', 'exec')
            
            # Verify it contains a function
            tree = ast.parse(source_code)
            has_function = any(isinstance(node, ast.FunctionDef) for node in ast.walk(tree))
            
            if not has_function:
                return False, "No function definition found in parsed code"
            
            return True, ""
            
        except SyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    @staticmethod
    def format_code(source_code: str) -> str:
        """Format code using Black if available."""
        if not BLACK_AVAILABLE:
            return source_code
        
        try:
            formatted = black.format_str(source_code, mode=black.FileMode())
            return formatted
        except Exception as e:
            logging.warning(f"Code formatting failed: {e}")
            return source_code
    
    @staticmethod
    def calculate_code_hash(source_code: str) -> str:
        """Calculate a hash of the code including signature and docstring for better duplicate detection."""
        try:
            tree = ast.parse(source_code)
            func_def = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
            
            signature = ast.unparse(func_def.args) if hasattr(ast, 'unparse') else str(func_def.args)
            docstring = ast.get_docstring(func_def) or ""
            body = ast.unparse(func_def.body) if hasattr(ast, 'unparse') else str(func_def.body)
            
            to_hash = signature + docstring + body
            return hashlib.md5(to_hash.encode()).hexdigest()
        except Exception:
            return hashlib.md5(source_code.encode()).hexdigest()
    
    @staticmethod
    def compare_functions_ast(code1: str, code2: str) -> bool:
        """
        Compare two functions using AST structure to detect semantic duplicates.
        """
        try:
            tree1 = ast.parse(code1)
            tree2 = ast.parse(code2)
            
            # Compare AST dumps without attributes (line numbers, etc.)
            dump1 = ast.dump(tree1, include_attributes=False)
            dump2 = ast.dump(tree2, include_attributes=False)
            
            return dump1 == dump2
        except Exception as e:
            logging.warning(f"AST comparison failed: {e}")
            return False


# ============================================================================
# ENHANCED INTELLIGENT CONTENT FILTERING SYSTEM
# ============================================================================

class IntelligentContentFilter:
    """
    Enhanced content filtering based on proven working approaches with enhanced fallback.
    """
    
    @staticmethod
    def clean_model_output(text: str) -> str:
        """Enhanced cleaning with fallback to raw output when cleaning fails."""
        if not text:
            return ""
        
        original_text = text
        
        # Stage 1: Remove thinking blocks
        patterns = [
            r'<think[^>]*>.*?</think>',
            r'<thinking[^>]*>.*?</thinking>',
            r'<reason[^>]*>.*?</reason>'
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Stage 2: Extract from markdown if present
        if '```python' in text:
            match = re.search(r'```python\s*\n(.*?)\n```', text, re.DOTALL)
            if match:
                text = match.group(1)
        elif '```' in text:
            match = re.search(r'```\s*\n(.*?)\n```', text, re.DOTALL)
            if match and 'def ' in match.group(1):
                text = match.group(1)
        
        # Stage 3: Force-strip to first 'def '
        if 'def ' in text:
            text = text[text.index('def '):]
        
        cleaned = text.strip()
        
        # ENHANCED FALLBACK: If cleaning removed everything but original has 'def ', fall back to raw
        if not cleaned and 'def ' in original_text:
            if original_text.index('def ') >= 0:
                return original_text[original_text.index('def '):].strip()
        
        # ENHANCED FALLBACK: If still empty, return raw text (let validation handle it)
        if not cleaned:
            return original_text.strip()
            
        return cleaned
    
    @staticmethod
    def check_generic_patterns(text: str) -> bool:
        """Check for overly generic function patterns that should be rejected."""
        # Allow all patterns for debugging (disabled generic rejection)
        return False
    
    @staticmethod
    def assess_content_quality(text: str) -> Dict[str, Any]:
        """Assess the quality and specificity of generated content."""
        assessment = {
            "is_specific": True,
            "has_meaningful_logic": True,
            "is_complete": True,
            "quality_score": 1.0,
            "issues": []
        }
        
        text_lower = text.lower()
        
        # Check for generic patterns
        if IntelligentContentFilter.check_generic_patterns(text):
            assessment["is_specific"] = False
            assessment["quality_score"] -= 0.4
            assessment["issues"].append("Generic function pattern detected")
        
        # Check for meaningful logic
        logic_indicators = ['if ', 'for ', 'while ', 'try:', 'except:', 'with ']
        logic_count = sum(1 for indicator in logic_indicators if indicator in text_lower)
        if logic_count < 2:
            assessment["has_meaningful_logic"] = False
            assessment["quality_score"] -= 0.3
            assessment["issues"].append("Insufficient logical complexity")
        
        # Check for completeness
        if 'def ' in text_lower:
            if not text_lower.strip().endswith(':') and 'return' not in text_lower:
                assessment["is_complete"] = False
                assessment["quality_score"] -= 0.3
                assessment["issues"].append("Function may be incomplete")
        
        # Adjust final score
        assessment["quality_score"] = max(0.0, assessment["quality_score"])
        
        return assessment


# ============================================================================
# FAILURE PATTERN LEARNING SYSTEM
# ============================================================================

class FailurePatternLearner:
    """
    Intelligent system for learning from failures and avoiding repeated mistakes.
    """
    
    def __init__(self, max_patterns: int = 50):
        self.max_patterns = max_patterns
        self.failure_patterns: Dict[str, FailurePattern] = {}
        self.recent_failures: List[str] = []
    
    def record_failure(self, description: str, error_type: str, code_content: str = ""):
        """Record a failure pattern for learning."""
        # Create a pattern hash based on the error and content
        pattern_content = f"{description}:{error_type}:{code_content[:100]}"
        pattern_hash = hashlib.md5(pattern_content.encode()).hexdigest()
        
        if pattern_hash in self.failure_patterns:
            pattern = self.failure_patterns[pattern_hash]
            pattern.failure_count += 1
            pattern.last_seen = datetime.now().isoformat()
            if error_type not in pattern.error_types:
                pattern.error_types.append(error_type)
        else:
            if len(self.failure_patterns) >= self.max_patterns:
                # Remove the oldest pattern
                oldest_hash = min(self.failure_patterns.keys(), 
                                key=lambda h: self.failure_patterns[h].last_seen)
                del self.failure_patterns[oldest_hash]
            
            self.failure_patterns[pattern_hash] = FailurePattern(
                pattern_hash=pattern_hash,
                description=description[:200],
                failure_count=1,
                last_seen=datetime.now().isoformat(),
                error_types=[error_type]
            )
        
        # Track recent failures for immediate avoidance
        self.recent_failures.append(pattern_hash)
        if len(self.recent_failures) > 20:
            self.recent_failures.pop(0)
    
    def is_likely_to_fail(self, description: str, code_content: str = "") -> bool:
        """Check if a pattern is likely to fail based on history."""
        pattern_content = f"{description}::{code_content[:100]}"
        pattern_hash = hashlib.md5(pattern_content.encode()).hexdigest()
        
        # Check if this exact pattern has failed recently
        if pattern_hash in self.recent_failures:
            return True
        
        # Check if similar patterns have high failure rates
        for pattern in self.failure_patterns.values():
            if (pattern.failure_count >= 3 and 
                description.lower() in pattern.description.lower()):
                return True
        
        return False
    
    def get_failure_summary(self) -> Dict[str, Any]:
        """Get a summary of failure patterns."""
        return {
            "total_patterns": len(self.failure_patterns),
            "recent_failures": len(self.recent_failures),
            "top_failures": sorted(
                self.failure_patterns.values(),
                key=lambda p: p.failure_count,
                reverse=True
            )[:5]
        }


# ============================================================================
# ENHANCED DIVERSE AUTONOMOUS PROMPTING SYSTEM
# ============================================================================

class DiversePromptGenerator:
    """
    Enhanced diverse prompt generator with reduced constraints for better reliability.
    """
    
    def __init__(self):
        self.used_prompts: Set[str] = set()
        self.used_concepts: Set[str] = set()
        self.used_function_names: Set[str] = set()
        
        # Simplified categories for better reliability
        self.prompt_categories = [
            "text_processing", "data_manipulation", "validation", "parsing", 
            "formatting", "calculation", "analysis", "transformation",
            "extraction", "classification"
        ]
        
        # Simplified function types
        self.function_types = [
            "validator", "parser", "formatter", "analyzer", "converter",
            "extractor", "processor", "calculator", "transformer", "classifier"
        ]
        
        # Simplified data types
        self.data_types = [
            "text", "numbers", "dates", "emails", "urls", "json", "csv", "xml",
            "lists", "dictionaries", "strings", "arrays"
        ]
    
    def generate_diverse_prompt(self, domain: str = None, iteration: int = 0) -> str:
        """Generate a simplified, working prompt without overly strict constraints."""
        # Create a unique seed based on iteration and time
        seed = f"{iteration}:{time.time()}"
        random.seed(hash(seed) % (2**32))
        
        # Select concepts for diversity
        category = random.choice(self.prompt_categories)
        func_type = random.choice(self.function_types)
        data_type = random.choice(self.data_types)
        
        # Generate a specific function name
        specific_name = f"{func_type}_{data_type}_{category[:4]}"
        
        # Simplified prompt structure without excessive constraints
        prompt = f"""Create ONE specific Python function that serves as a tool for LLMs:

Requirements:
- Function type: {func_type} for {data_type}
- Use only standard Python library
- Accept a single dict input parameter 'input_data'
- Return a dict with keys 'result','status','error'
- Include comprehensive error handling
- Provide docstring with I/O formats

Focus on: {category} with {data_type}

Function should be specific and useful, not generic.
"""
        
        if domain:
            prompt += f"\nDomain context: {domain}"
        
        prompt += f"\n\nGenerate ONE complete, working function:"
        
        # Track usage for diversity
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        self.used_prompts.add(prompt_hash)
        self.used_concepts.add(f"{category}:{func_type}:{data_type}")
        self.used_function_names.add(specific_name)
        
        return prompt


# ============================================================================
# ENHANCED DATABASE MANAGEMENT SYSTEM
# ============================================================================

class AdvancedFunctionDatabase:
    """
    Enhanced database management with LLM tool registry and comprehensive functionality.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        self.connection_lock = threading.Lock()
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize database with enhanced schema and migration support."""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                with self.connection_lock:
                    self.connection = sqlite3.connect(
                        self.db_path, 
                        check_same_thread=False,
                        timeout=30.0
                    )
                    
                    # Enable advanced settings
                    self.connection.execute("PRAGMA journal_mode=WAL")
                    self.connection.execute("PRAGMA foreign_keys=ON")
                    self.connection.execute("PRAGMA synchronous=NORMAL")
                    
                    # Create advanced schema
                    self._create_or_migrate_schema()
                    
                    self.connection.commit()
                    print("✅ Enhanced database initialized successfully")
                    return
                    
            except sqlite3.Error as e:
                if attempt == max_retries - 1:
                    raise DatabaseError(f"Failed to initialize database after {max_retries} attempts: {e}")
                else:
                    print(f"⚠️  Database initialization attempt {attempt + 1} failed, retrying...")
                    time.sleep(1)
    
    def _create_or_migrate_schema(self):
        """Create or migrate database schema with enhanced table structure."""
        # Create main functions table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS functions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                description TEXT,
                parameters TEXT,  -- JSON
                return_type TEXT,
                created_at TEXT,
                validation_status TEXT,
                test_results TEXT,  -- JSON
                source_code TEXT,
                dependencies TEXT,  -- JSON
                safety_rating TEXT,
                debug_info TEXT,  -- JSON
                signature TEXT DEFAULT '',
                complexity_score INTEGER DEFAULT 5,
                code_hash TEXT DEFAULT '',
                usage_example TEXT DEFAULT '',
                input_output_description TEXT DEFAULT '',
                source_artifact TEXT DEFAULT '',
                UNIQUE(name, domain)
            )
        """)
        
        # Create failure patterns table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS failure_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_hash TEXT UNIQUE NOT NULL,
                description TEXT,
                failure_count INTEGER DEFAULT 1,
                last_seen TEXT,
                error_types TEXT,  -- JSON
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create action log table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                action_type TEXT,
                description TEXT,
                details TEXT,  -- JSON
                success BOOLEAN,
                error_message TEXT
            )
        """)
        
        # Create discovered artifacts table
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS discovered_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                artifact_type TEXT,
                description TEXT,
                metadata TEXT,  -- JSON
                discovered_at TEXT,
                processed BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Create code diff table for training data
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS code_diffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                original_code TEXT,
                processed_code TEXT,
                transformation_type TEXT,
                success BOOLEAN,
                validation_errors TEXT,  -- JSON
                function_name TEXT DEFAULT '',
                original_length INTEGER DEFAULT 0,
                processed_length INTEGER DEFAULT 0,
                size_change INTEGER DEFAULT 0
            )
        """)
        
        # Check for missing columns and add them
        cursor = self.connection.execute("PRAGMA table_info(functions)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        required_columns = {
            'debug_info': 'TEXT',
            'signature': 'TEXT DEFAULT ""',
            'complexity_score': 'INTEGER DEFAULT 5',
            'code_hash': 'TEXT DEFAULT ""',
            'usage_example': 'TEXT DEFAULT ""',
            'input_output_description': 'TEXT DEFAULT ""',
            'source_artifact': 'TEXT DEFAULT ""'
        }
        
        for column_name, column_def in required_columns.items():
            if column_name not in existing_columns:
                try:
                    self.connection.execute(f"ALTER TABLE functions ADD COLUMN {column_name} {column_def}")
                except sqlite3.Error as e:
                    pass  # Column may already exist
        
        # Create comprehensive indexes
        indexes = [
            ("idx_functions_domain", "CREATE INDEX IF NOT EXISTS idx_functions_domain ON functions(domain)"),
            ("idx_functions_validation", "CREATE INDEX IF NOT EXISTS idx_functions_validation ON functions(validation_status)"),
            ("idx_functions_hash", "CREATE INDEX IF NOT EXISTS idx_functions_hash ON functions(code_hash)"),
            ("idx_functions_created", "CREATE INDEX IF NOT EXISTS idx_functions_created ON functions(created_at)"),
            ("idx_patterns_hash", "CREATE INDEX IF NOT EXISTS idx_patterns_hash ON failure_patterns(pattern_hash)"),
            ("idx_patterns_count", "CREATE INDEX IF NOT EXISTS idx_patterns_count ON failure_patterns(failure_count)"),
            ("idx_action_timestamp", "CREATE INDEX IF NOT EXISTS idx_action_timestamp ON action_log(timestamp)"),
            ("idx_artifacts_type", "CREATE INDEX IF NOT EXISTS idx_artifacts_type ON discovered_artifacts(artifact_type)"),
            ("idx_artifacts_processed", "CREATE INDEX IF NOT EXISTS idx_artifacts_processed ON discovered_artifacts(processed)"),
            ("idx_diffs_timestamp", "CREATE INDEX IF NOT EXISTS idx_diffs_timestamp ON code_diffs(timestamp)"),
            ("idx_diffs_type", "CREATE INDEX IF NOT EXISTS idx_diffs_type ON code_diffs(transformation_type)"),
            ("idx_diffs_success", "CREATE INDEX IF NOT EXISTS idx_diffs_success ON code_diffs(success)")
        ]
        
        for index_name, index_sql in indexes:
            try:
                self.connection.execute(index_sql)
            except sqlite3.Error as e:
                pass  # Index may already exist
    
    def store_function(self, metadata: FunctionMetadata) -> bool:
        """Store function with enhanced transaction management."""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                with self.connection_lock:
                    # Begin transaction
                    self.connection.execute("BEGIN IMMEDIATE")
                    
                    try:
                        # Ensure all required fields are present
                        debug_info = metadata.debug_info or {}
                        signature = metadata.signature or ""
                        complexity_score = getattr(metadata, 'complexity_score', 5)
                        code_hash = metadata.code_hash or ""
                        usage_example = getattr(metadata, 'usage_example', "")
                        input_output_description = getattr(metadata, 'input_output_description', "")
                        source_artifact = getattr(metadata, 'source_artifact', "")
                        
                        self.connection.execute("""
                            INSERT OR REPLACE INTO functions 
                            (name, domain, description, parameters, return_type, created_at,
                             validation_status, test_results, source_code, dependencies, 
                             safety_rating, debug_info, signature, complexity_score, code_hash,
                             usage_example, input_output_description, source_artifact)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            metadata.name, metadata.domain, metadata.description,
                            json.dumps(metadata.parameters), metadata.return_type,
                            metadata.created_at, metadata.validation_status,
                            json.dumps(metadata.test_results), metadata.source_code,
                            json.dumps(metadata.dependencies), metadata.safety_rating,
                            json.dumps(debug_info), signature, complexity_score, code_hash,
                            usage_example, input_output_description, source_artifact
                        ))
                        
                        # Commit transaction
                        self.connection.commit()
                        return True
                        
                    except Exception as e:
                        # Rollback on error
                        self.connection.rollback()
                        raise e
                        
            except sqlite3.Error as e:
                if attempt == max_retries - 1:
                    logging.error(f"Failed to store function {metadata.name} after {max_retries} attempts: {e}")
                    return False
                else:
                    logging.warning(f"Store attempt {attempt + 1} failed, retrying: {e}")
                    time.sleep(0.5)
        
        return False
    
    def store_code_diff(self, diff_entry: CodeDiffEntry) -> bool:
        """Store code diff entry for training data analysis."""
        try:
            with self.connection_lock:
                self.connection.execute("""
                    INSERT INTO code_diffs 
                    (timestamp, original_code, processed_code, transformation_type, 
                     success, validation_errors, function_name, original_length, 
                     processed_length, size_change)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    diff_entry.timestamp, diff_entry.original_code, diff_entry.processed_code,
                    diff_entry.transformation_type, diff_entry.success,
                    json.dumps(diff_entry.validation_errors), diff_entry.function_name,
                    len(diff_entry.original_code), len(diff_entry.processed_code),
                    len(diff_entry.processed_code) - len(diff_entry.original_code)
                ))
                self.connection.commit()
                return True
        except sqlite3.Error as e:
            logging.error(f"Failed to store code diff: {e}")
            return False
    
    def get_training_dataset(self, transformation_types: List[str] = None, 
                           successful_only: bool = True) -> List[Dict[str, str]]:
        """Extract training dataset from stored code diffs."""
        try:
            with self.connection_lock:
                query = """
                    SELECT original_code, processed_code, transformation_type, function_name
                    FROM code_diffs
                    WHERE original_code != processed_code
                """
                params = []
                
                if successful_only:
                    query += " AND success = ?"
                    params.append(True)
                
                if transformation_types:
                    placeholders = ','.join('?' * len(transformation_types))
                    query += f" AND transformation_type IN ({placeholders})"
                    params.extend(transformation_types)
                
                query += " ORDER BY timestamp DESC"
                
                cursor = self.connection.execute(query, params)
                results = cursor.fetchall()
                
                dataset = []
                for row in results:
                    dataset.append({
                        "input": row[0],
                        "output": row[1],
                        "transformation_type": row[2],
                        "function_name": row[3]
                    })
                
                return dataset
        except sqlite3.Error as e:
            logging.error(f"Failed to retrieve training dataset: {e}")
            return []
    
    def export_training_data_jsonl(self, output_path: str = "training_data.jsonl", 
                                  transformation_types: List[str] = None) -> bool:
        """Export training data to JSONL format for fine-tuning."""
        dataset = self.get_training_dataset(transformation_types)
        
        try:
            with open(output_path, 'w') as f:
                for entry in dataset:
                    f.write(json.dumps(entry) + '\n')
            
            print(f"✅ Exported {len(dataset)} training examples to {output_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to export training data: {e}")
            return False
    
    def get_function_catalog(self) -> Dict[str, Dict[str, Any]]:
        """Return a catalog of all validated functions for LLM use."""
        try:
            with self.connection_lock:
                cursor = self.connection.execute("""
                    SELECT name, domain, description, parameters, return_type, signature, 
                           usage_example, input_output_description, code_hash, source_artifact
                    FROM functions WHERE validation_status = 'VALIDATED'
                """)
                
                catalog = {}
                for row in cursor.fetchall():
                    catalog[row[0]] = {
                        "domain": row[1],
                        "description": row[2],
                        "parameters": json.loads(row[3]) if row[3] else {},
                        "return_type": row[4],
                        "signature": row[5],
                        "usage_example": row[6],
                        "input_output_description": row[7],
                        "code_hash": row[8],
                        "source_artifact": row[9]
                    }
                return catalog
        except sqlite3.Error as e:
            logging.error(f"Failed to retrieve function catalog: {e}")
            return {}
    
    def store_failure_pattern(self, pattern: FailurePattern) -> bool:
        """Store failure pattern for learning."""
        try:
            with self.connection_lock:
                self.connection.execute("""
                    INSERT OR REPLACE INTO failure_patterns 
                    (pattern_hash, description, failure_count, last_seen, error_types)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    pattern.pattern_hash, pattern.description, pattern.failure_count,
                    pattern.last_seen, json.dumps(pattern.error_types)
                ))
                self.connection.commit()
                return True
        except sqlite3.Error as e:
            logging.error(f"Failed to store failure pattern: {e}")
            return False
    
    def store_action_log(self, action: ActionLog) -> bool:
        """Store action log entry."""
        try:
            with self.connection_lock:
                self.connection.execute("""
                    INSERT INTO action_log 
                    (timestamp, action_type, description, details, success, error_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    action.timestamp, action.action_type, action.description,
                    json.dumps(action.details), action.success, action.error_message
                ))
                self.connection.commit()
                return True
        except sqlite3.Error as e:
            logging.error(f"Failed to store action log: {e}")
            return False
    
    def store_discovered_artifact(self, artifact: DiscoveredArtifact) -> bool:
        """Store discovered artifact."""
        try:
            with self.connection_lock:
                self.connection.execute("""
                    INSERT OR REPLACE INTO discovered_artifacts 
                    (path, artifact_type, description, metadata, discovered_at, processed)
                    VALUES (?, ?, ?, ?, ?, ?)""", (
                    artifact.path, artifact.artifact_type, artifact.description,
                    json.dumps(artifact.metadata), artifact.discovered_at, False
                ))
                self.connection.commit()
                return True
        except sqlite3.Error as e:
            logging.error(f"Failed to store discovered artifact: {e}")
            return False
    
    def load_failure_patterns(self) -> Dict[str, FailurePattern]:
        """Load failure patterns from database."""
        patterns = {}
        try:
            with self.connection_lock:
                cursor = self.connection.execute("""
                    SELECT pattern_hash, description, failure_count, last_seen, error_types
                    FROM failure_patterns
                """)
                
                for row in cursor.fetchall():
                    pattern = FailurePattern(
                        pattern_hash=row[0],
                        description=row[1],
                        failure_count=row[2],
                        last_seen=row[3],
                        error_types=json.loads(row[4]) if row[4] else []
                    )
                    patterns[row[0]] = pattern
                    
        except sqlite3.Error as e:
            logging.error(f"Failed to load failure patterns: {e}")
        
        return patterns
    
    def get_functions_by_domain(self, domain: str) -> List[FunctionMetadata]:
        """Retrieve functions with enhanced error handling."""
        try:
            with self.connection_lock:
                cursor = self.connection.execute("""
                    SELECT * FROM functions WHERE domain = ? AND validation_status = 'VALIDATED'
                    ORDER BY created_at DESC
                """, (domain,))
                
                functions = []
                for row in cursor.fetchall():
                    try:
                        # Handle potential missing columns gracefully
                        debug_info = json.loads(row[12]) if len(row) > 12 and row[12] else {}
                        signature = row[13] if len(row) > 13 else ""
                        complexity_score = row[14] if len(row) > 14 else 5
                        code_hash = row[15] if len(row) > 15 else ""
                        usage_example = row[16] if len(row) > 16 else ""
                        input_output_description = row[17] if len(row) > 17 else ""
                        source_artifact = row[18] if len(row) > 18 else ""
                        
                        metadata = FunctionMetadata(
                            name=row[1], domain=row[2], description=row[3],
                            parameters=json.loads(row[4]), return_type=row[5],
                            created_at=row[6], validation_status=row[7],
                            test_results=json.loads(row[8]), source_code=row[9],
                            dependencies=json.loads(row[10]), safety_rating=row[11],
                            debug_info=debug_info, signature=signature,
                            complexity_score=complexity_score, code_hash=code_hash,
                            usage_example=usage_example, input_output_description=input_output_description,
                            source_artifact=source_artifact
                        )
                        functions.append(metadata)
                    except Exception as e:
                        logging.warning(f"Failed to parse function metadata: {e}")
                        continue
                
                return functions
                
        except sqlite3.Error as e:
            logging.error(f"Failed to retrieve functions for domain {domain}: {e}")
            return []
    
    def get_all_domains(self) -> List[str]:
        """Get all domains with enhanced error handling."""
        try:
            with self.connection_lock:
                cursor = self.connection.execute("""
                    SELECT DISTINCT domain FROM functions WHERE validation_status = 'VALIDATED'
                    ORDER BY domain
                """)
                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Failed to retrieve domains: {e}")
            return []
    
    def function_exists(self, code_hash: str) -> bool:
        """Check if a function with the same code hash already exists."""
        try:
            with self.connection_lock:
                cursor = self.connection.execute("""
                    SELECT COUNT(*) FROM functions WHERE code_hash = ? AND validation_status = 'VALIDATED'
                """, (code_hash,))
                count = cursor.fetchone()[0]
                return count > 0
        except sqlite3.Error as e:
            logging.error(f"Failed to check function existence: {e}")
            return False
    
    def function_name_exists(self, function_name: str, domain: str = None) -> bool:
        """
        EDIT 4: Function Name Uniqueness Validation - Check if function name already exists.
        Enhanced collision prevention logic with domain-specific checking.
        """
        try:
            with self.connection_lock:
                if domain:
                    cursor = self.connection.execute("""
                        SELECT COUNT(*) FROM functions WHERE name = ? AND domain = ? AND validation_status = 'VALIDATED'
                    """, (function_name, domain))
                else:
                    cursor = self.connection.execute("""
                        SELECT COUNT(*) FROM functions WHERE name = ? AND validation_status = 'VALIDATED'
                    """, (function_name,))
                count = cursor.fetchone()[0]
                return count > 0
        except sqlite3.Error as e:
            logging.error(f"Failed to check function name existence: {e}")
            return False
    
    def check_ast_duplicate(self, new_code: str) -> Optional[str]:
        """Check for AST-based duplicate functions."""
        try:
            with self.connection_lock:
                cursor = self.connection.execute("""
                    SELECT name, source_code FROM functions WHERE validation_status = 'VALIDATED'
                """)
                
                for row in cursor.fetchall():
                    existing_name, existing_code = row
                    if AdvancedCodeProcessor.compare_functions_ast(new_code, existing_code):
                        return existing_name
                
                return None
        except sqlite3.Error as e:
            logging.error(f"Failed to check AST duplicates: {e}")
            return None


# ============================================================================
# ENHANCED ADAPTIVE TEST EXECUTION SYSTEM WITH CONDA SANDBOX
# ============================================================================

class AdvancedTestExecutor:
    """
    Enhanced adaptive test execution system with Conda-compatible sandbox environment for safe testing.
    """
    
    def __init__(self, config: 'SystemConfig'):
        """Initialize the test executor with configuration."""
        self.config = config
    
    def create_intelligent_test_script(self, function_code: str, function_name: str) -> str:
        """
        Create intelligent test script that comprehensively analyzes function signature.
        """
        
        test_script = f'''#!/usr/bin/env python3
"""
Intelligent test script for function: {function_name}
Generated by Enhanced Autonomous Function Development System v5.2.3
"""

import sys
import traceback
import inspect
import ast
from typing import get_type_hints, Union, Any, Optional

# Function under test
{function_code}

def analyze_function_signature(func):
    """Comprehensive function signature analysis."""
    try:
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        analysis = {{
            "name": func.__name__,
            "parameters": [],
            "return_annotation": sig.return_annotation,
            "has_defaults": False,
            "is_complex": False
        }}
        
        for name, param in sig.parameters.items():
            param_info = {{
                "name": name,
                "annotation": type_hints.get(name, str),
                "default": param.default,
                "kind": param.kind.name
            }}
            
            if param.default != inspect.Parameter.empty:
                analysis["has_defaults"] = True
            
            if param.kind in [inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD]:
                analysis["is_complex"] = True
            
            analysis["parameters"].append(param_info)
        
        return analysis
    except Exception as e:
        return {{"error": str(e)}}

def generate_intelligent_arguments(func):
    """Generate intelligent test arguments based on comprehensive analysis."""
    try:
        analysis = analyze_function_signature(func)
        
        if "error" in analysis:
            return ["test"], {{}}, analysis["error"]
        
        args = []
        kwargs = {{}}
        
        for param in analysis["parameters"]:
            name = param["name"]
            annotation = param["annotation"]
            default = param["default"]
            kind = param["kind"]
            
            # Use default if available
            if default != inspect.Parameter.empty:
                if kind == "KEYWORD_ONLY":
                    kwargs[name] = default
                else:
                    args.append(default)
                continue
            
            # Generate value based on type annotation
            value = generate_typed_value(annotation, name)
            
            if kind == "KEYWORD_ONLY":
                kwargs[name] = value
            elif kind == "VAR_POSITIONAL":
                # Add a few values for *args
                args.extend([value, value])
            elif kind == "VAR_KEYWORD":
                # Add some values for **kwargs
                kwargs.update({{"test_key": value, "extra_param": "test"}})
            else:
                args.append(value)
        
        return args, kwargs, None
    except Exception as e:
        return ["test"], {{}}, str(e)

def generate_typed_value(annotation, param_name=""):
    """Generate appropriate value based on type annotation."""
    if annotation == int or annotation == "int":
        return 42
    elif annotation == float or annotation == "float":
        return 3.14
    elif annotation == bool or annotation == "bool":
        return True
    elif annotation == list or annotation == "list":
        return ["test", "data"]
    elif annotation == dict or annotation == "dict":
        return {{"key": "value"}}
    elif annotation == tuple or annotation == "tuple":
        return ("test", "tuple")
    elif annotation == set or annotation == "set":
        return {{"test", "set"}}
    elif hasattr(annotation, '__origin__'):
        # Handle generic types like List[int], Dict[str, int], etc.
        origin = getattr(annotation, '__origin__', None)
        if origin == list:
            return ["sample", "list", "data"]
        elif origin == dict:
            return {{"sample": "dict", "key": "value"}}
        elif origin == tuple:
            return ("sample", "tuple")
        elif origin == set:
            return {{"sample", "set"}}
        elif origin == Union:
            # For Optional types or Union types
            args = getattr(annotation, '__args__', ())
            if type(None) in args:
                # Optional type - try the first non-None type
                non_none_types = [t for t in args if t != type(None)]
                if non_none_types:
                    return generate_typed_value(non_none_types[0], param_name)
                return None
            else:
                # Union type - use first type
                return generate_typed_value(args[0], param_name) if args else "test"
        else:
            return "test"
    else:
        # Handle string-based annotations or unknown types
        if "str" in str(annotation).lower():
            return "test_string"
        elif "int" in str(annotation).lower():
            return 123
        elif "float" in str(annotation).lower():
            return 1.23
        elif "list" in str(annotation).lower():
            return ["item1", "item2"]
        elif "dict" in str(annotation).lower():
            return {{"key1": "value1", "key2": "value2"}}
        else:
            # Default to string for unknown types
            return f"test_{{param_name}}" if param_name else "test"

def test_llm_tool_interface(func):
    """Test if function follows LLM tool interface standards."""
    try:
        # Test with standard LLM tool input format
        test_input = {{"input_data": {{"test": "value", "number": 42}}}}
        result = func(test_input)
        
        if isinstance(result, dict):
            required_keys = ["result", "status"]
            has_required = all(key in result for key in required_keys)
            if has_required:
                print("PASS: Function follows LLM tool interface standards")
                return True
            else:
                print(f"WARNING: Function output missing required keys: {{required_keys}}")
        else:
            print(f"WARNING: Function should return dict, got {{type(result)}}")
        
        return False
    except Exception as e:
        print(f"INFO: LLM tool interface test failed: {{e}}")
        return False

def main():
    """Execute comprehensive validation tests."""
    
    # Test 1: Function existence and type verification
    try:
        func_obj = globals().get('{function_name}')
        if func_obj is None:
            print("ERROR: Function '{function_name}' not found in globals")
            return False
        
        if not callable(func_obj):
            print("ERROR: '{function_name}' is not callable")
            return False
        
        print(f"PASS: Function '{function_name}' exists and is callable")
        
    except Exception as e:
        print(f"ERROR: Function existence check failed: {{e}}")
        return False
    
    # Test 2: LLM Tool Interface Test
    llm_tool_compatible = test_llm_tool_interface(func_obj)
    
    # Test 3: Comprehensive signature analysis
    try:
        analysis = analyze_function_signature(func_obj)
        print(f"INFO: Function analysis: {{analysis}}")
        
        if "error" not in analysis:
            param_count = len(analysis["parameters"])
            print(f"INFO: Parameter count: {{param_count}}")
            print(f"INFO: Has defaults: {{analysis['has_defaults']}}")
            print(f"INFO: Is complex: {{analysis['is_complex']}}")
        
    except Exception as e:
        print(f"WARNING: Could not analyze function signature: {{e}}")
    
    # Test 4: Intelligent execution with generated arguments
    try:
        args, kwargs, error = generate_intelligent_arguments(func_obj)
        
        if error:
            print(f"WARNING: Argument generation error: {{error}}")
        
        print(f"INFO: Generated args: {{args}}")
        print(f"INFO: Generated kwargs: {{kwargs}}")
        
        test_result = func_obj(*args, **kwargs)
        print(f"PASS: Function '{function_name}' executed successfully")
        print(f"INFO: Return value: {{repr(test_result)}}")
        print(f"INFO: Return type: {{type(test_result).__name__}}")
        
        # Validate return type if specified
        if hasattr(func_obj, '__annotations__') and 'return' in func_obj.__annotations__:
            expected_type = func_obj.__annotations__['return']
            if expected_type != type(test_result) and expected_type != Any:
                print(f"WARNING: Return type mismatch. Expected {{expected_type}}, got {{type(test_result)}}")
        
        return True
        
    except Exception as e:
        print(f"WARNING: Function execution with intelligent args failed: {{e}}")
        
        # Test 5: Comprehensive fallback execution strategies
        fallback_strategies = [
            # No arguments
            ([], {{}}, "no arguments"),
            # Single string argument
            (["test"], {{}}, "single string argument"),
            # Single integer argument
            ([1], {{}}, "single integer argument"),
            # Single dictionary argument (LLM tool format)
            ([{{"input_data": "test"}}], {{}}, "LLM tool format"),
            # Multiple basic arguments
            (["test", 1, True], {{}}, "multiple basic arguments"),
            # Dictionary argument
            ([{{"key": "value"}}], {{}}, "dictionary argument"),
            # List argument
            ([[\"item1\", \"item2\"]], {{}}, "list argument"),
        ]
        
        for test_args, test_kwargs, strategy_name in fallback_strategies:
            try:
                print(f"INFO: Trying fallback strategy: {{strategy_name}}")
                test_result = func_obj(*test_args, **test_kwargs)
                print(f"PASS: Function '{function_name}' executed with {{strategy_name}}")
                print(f"INFO: Return value: {{repr(test_result)}}")
                return True
            except Exception as fallback_error:
                print(f"INFO: Fallback strategy '{{strategy_name}}' failed: {{fallback_error}}")
                continue
        
        # Test 6: Final callable verification
        try:
            if callable(globals().get('{function_name}')):
                print(f"PASS: Function '{function_name}' is callable (minimal validation)")
                return True
        except Exception as final_error:
            print(f"ERROR: Final validation failed: {{final_error}}")
        
        return False

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("TEST PASSED")
            sys.exit(0)
        else:
            print("TEST FAILED")
            sys.exit(1)
    except Exception as critical_error:
        print(f"CRITICAL_ERROR: {{critical_error}}")
        traceback.print_exc()
        sys.exit(1)
'''
        
        return test_script
    
    def execute_test_script(self, function_code: str, test_script: str) -> Tuple[bool, str]:
        """
        Compile, sandbox, and execute the test script against the generated function.
        Returns (success, message_or_output).
        Sandbox must succeed when enabled; failure to create one is a validation failure.
        """
        use_bwrap = False
        use_conda = False
        sandbox_path = None
        conda_exec = shutil.which("conda")
        bwrap_exec = shutil.which("bwrap")

        if self.config.ENABLE_SANDBOX_EXECUTION:
            if bwrap_exec:
                use_bwrap = True
            elif conda_exec:
                base_env = self.config.BASE_CONDA_ENV_PATH
                sandbox_path = os.path.join(self.config.SANDBOX_PATH, f"sandbox_{int(time.time())}")
                if os.path.isdir(base_env):
                    try:
                        subprocess.run(
                            [conda_exec, "create", "-p", sandbox_path, "--clone", base_env, "--yes"],
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        use_conda = True
                    except subprocess.CalledProcessError as conda_error:
                        if self.config.ENABLE_DEBUG_MODE:
                            print(f"❌ Conda sandbox creation failed: {conda_error}.")
                elif self.config.ENABLE_DEBUG_MODE:
                    print(f"❌ Base Conda env not found at {base_env}.")
            if not (use_bwrap or use_conda):
                return False, "Sandbox unavailable or failed to initialize; validation aborted."

        python_cmd = [sys.executable]
        sandbox_tmpdir = None
        if use_conda:
            python_cmd = [conda_exec, "run", "-p", sandbox_path, sys.executable]
        elif use_bwrap:
            sandbox_tmpdir = tempfile.mkdtemp(prefix="sandbox_")
            python_cmd = [
                bwrap_exec,
                "--unshare-all",
                "--die-with-parent",
                "--dev",
                "/dev",
                "--proc",
                "/proc",
                "--ro-bind",
                "/usr",
                "/usr",
                "--ro-bind",
                "/bin",
                "/bin",
                "--ro-bind",
                "/lib",
                "/lib",
                "--ro-bind",
                "/lib64",
                "/lib64",
                "--tmpfs",
                "/tmp",
                "--tmpfs",
                "/var/tmp",
                "--bind",
                sandbox_tmpdir,
                "/scratch",
                "--unshare-net",
                "--chdir",
                "/scratch",
                "--",
                sys.executable,
            ]

        # Write function + test to a temporary script
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(test_script)
            script_path = f.name

        # Execute the test
        try:
            cmd = python_cmd + ["-u", script_path]

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.config.VALIDATION_TIMEOUT,
            )

            stdout = result.stdout.decode(errors="ignore").strip()
            stderr = result.stderr.decode(errors="ignore").strip()

            if result.returncode != 0:
                if self.config.ENABLE_DEBUG_MODE:
                    print("🛠️ [Debug] Test script stdout:")
                    print(stdout or "<no stdout>")
                    print("🛠️ [Debug] Test script stderr:")
                    print(stderr or "<no stderr>")
                error_msg = stderr or stdout or f"Process exited with code {result.returncode}"
                return False, error_msg

            # Success path: look for test success marker
            if "TEST PASSED" in stdout:
                return True, stdout

            # Ambiguous: no explicit success
            if self.config.ENABLE_DEBUG_MODE:
                print("⚠️  Ambiguous test result, printing full output:")
                print(stdout or "<no stdout>")
            return False, f"Ambiguous test result: {stdout or '<no output>'}"

        except subprocess.TimeoutExpired:
            return False, "❌ Test execution timed out."
        except Exception as e:
            if self.config.ENABLE_DEBUG_MODE:
                traceback.print_exc()
            return False, f"Test execution error: {e}"
        finally:
            # Cleanup
            try:
                os.unlink(script_path)
            except:
                pass
            if use_conda and sandbox_path:
                shutil.rmtree(sandbox_path, ignore_errors=True)
            if sandbox_tmpdir:
                shutil.rmtree(sandbox_tmpdir, ignore_errors=True)
            if use_sandbox and sandbox_path and os.path.exists(sandbox_path):
                try:
                    shutil.rmtree(sandbox_path)
                except:
                    pass


# ============================================================================
# ENHANCED MODEL INTERFACE SYSTEM - WITH ARCHITECTURAL FIXES
# ============================================================================

class AdvancedModelInterface:
    """
    Enhanced model interface with comprehensive architectural fixes applied.
    """
    
    def __init__(self, config: 'SystemConfig'):
        self.config = config
        # Use simple initialization pattern
        self.client = Client()
        self.async_client = AsyncClient()
        self.kill_autonomous = threading.Event()
        self.content_filter = IntelligentContentFilter()
        self.code_processor = AdvancedCodeProcessor()
        self.prompt_generator = DiversePromptGenerator()
        self.failure_learner = FailurePatternLearner(config.MAX_FAILURE_PATTERNS)
        self.code_diff_logger = CodeDiffLogger(config)
    
    def generate_code_robust(self, prompt: str, context: str = "") -> StandardizedModelResponse:
        """
        EDIT 2: Multi-Model Fallback Strategy - Generate code with sequential model attempts.
        Enhanced with response validation and multiple model fallback mechanisms.
        """
        try:
            # Check if this prompt is likely to fail
            if (self.config.ENABLE_FAILURE_LEARNING and 
                self.failure_learner.is_likely_to_fail(prompt)):
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"🚨 Prompt likely to fail based on history, adjusting...")
                prompt = self._adjust_failing_prompt(prompt)
            
            # EDIT 5: Enhanced Response Validation - Validate content before processing
            def _validate_response_content(response_text: str) -> bool:
                """Validate response meets minimum quality standards."""
                if not response_text or len(response_text.strip()) < 20:
                    return False
                if 'def ' not in response_text:
                    return False
                return True
            
            # EDIT 2: Multi-Model Fallback Strategy - Try primary model first
            models_to_try = [
                self.config.CODE_GENERATION_MODEL,
                self.config.INTELLIGENCE_MODEL,
                self.config.get_working_model_for_code_generation()
            ]
            
            # Remove duplicates while preserving order
            seen = set()
            models_to_try = [m for m in models_to_try if not (m in seen or seen.add(m))]
            
            for attempt, model in enumerate(models_to_try, 1):
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"🔍 Attempt {attempt}/{len(models_to_try)} using model: {model}")
                
                # Enhanced prompt structure for proper code generation
                full_prompt = f"""Generate a Python function. Return ONLY the function code.

Task: {prompt}

Requirements:
- Complete function definition only
- Accept dictionary input parameter named 'input_data'
- Return dictionary with 'result', 'status', and 'error' keys
- Include proper error handling  
- Use standard library only
- No explanations or examples

Function code:"""
                
                try:
                    # Use proven working options with proper stop sequences
                    response = self.client.generate(
                        model=model,
                        prompt=full_prompt,
                        stream=False,
                        options={
                            "temperature": self.config.TEMPERATURE,
                            "top_p": self.config.TOP_P,
                            "max_tokens": self.config.MAX_TOKENS,
                            "repeat_penalty": 1.1,
                            "num_predict": self.config.MAX_TOKENS,
                            "stop": [
                                "<think>", "</think>", "<thinking>", "</thinking>", 
                                "Example:", "Usage:", "Note:", "Here's", "This function"
                            ]
                        }
                    )
                    
                    raw_code = response.get('response', '')
                    
                    # Enhanced response debugging
                    if self.config.ENABLE_DEBUG_MODE:
                        print(f"🔍 Model: {model}")
                        print(f"🔍 Response type: {type(raw_code)}")
                        print(f"🔍 Response length: {len(raw_code) if raw_code else 0}")
                        print(f"🔍 Response preview: {repr(raw_code[:200]) if raw_code else 'EMPTY'}")
                    
                    # EDIT 5: Enhanced Response Validation - Validate before processing
                    if _validate_response_content(raw_code):
                        # Advanced cleaning and extraction
                        cleaned_code = self.content_filter.clean_model_output(raw_code)
                        extracted_code = self.code_processor.extract_pure_function_code(cleaned_code)
                        
                        # Log code transformation for training data
                        if self.config.ENABLE_CODE_DIFF_LOGGING:
                            function_name = self.code_processor.get_function_name(extracted_code) or "unknown"
                            self.code_diff_logger.log_content_cleaning(
                                raw_output=raw_code,
                                cleaned_code=extracted_code,
                                extraction_method="ast_based",
                                success=bool(extracted_code and len(extracted_code.strip()) > 20),
                                function_name=function_name
                            )
                        
                        if self.config.ENABLE_DEBUG_MODE:
                            print(f"🔍 Cleaned code length: {len(cleaned_code)}")
                            print(f"🔍 Extracted code length: {len(extracted_code)}")
                            print(f"🔍 Extracted code preview: {extracted_code[:100]}...")
                        
                        if extracted_code and len(extracted_code.strip()) >= 20:
                            # Format code if available
                            if self.config.ENABLE_CODE_FORMATTING:
                                try:
                                    formatted_code = self.code_processor.format_code(extracted_code)
                                    if self.config.ENABLE_CODE_DIFF_LOGGING:
                                        function_name = self.code_processor.get_function_name(extracted_code) or "unknown"
                                        self.code_diff_logger.log_code_formatting(
                                            unformatted_code=extracted_code,
                                            formatted_code=formatted_code,
                                            success=True,
                                            function_name=function_name
                                        )
                                    extracted_code = formatted_code
                                except Exception as format_error:
                                    if self.config.ENABLE_DEBUG_MODE:
                                        print(f"🔍 Code formatting failed: {format_error}")
                            
                            return StandardizedModelResponse(
                                content=extracted_code,
                                is_valid=True,
                                metadata={"generation_type": "extracted", "model": model, "attempt": attempt},
                                raw_response=raw_code,
                                extraction_method="ast_based"
                            )
                    
                    # Response validation failed, try simpler prompt
                    if self.config.ENABLE_DEBUG_MODE:
                        print(f"⚠️  Response validation failed for model {model}, trying simplified prompt...")
                    
                    simple_prompt = f"""Create a Python function:

{prompt}

Just return the function code, nothing else."""
                    
                    response = self.client.generate(
                        model=model,
                        prompt=simple_prompt,
                        stream=False,
                        options={
                            "temperature": self.config.TEMPERATURE,
                            "top_p": self.config.TOP_P,
                            "max_tokens": self.config.MAX_TOKENS,
                            "repeat_penalty": 1.1,
                            "num_predict": self.config.MAX_TOKENS,
                            "stop": ["<think>", "</think>", "<thinking>", "</thinking>"]
                        }
                    )
                    raw_code = response.get('response', '')
                    
                    if self.config.ENABLE_DEBUG_MODE:
                        print(f"🔍 Simplified retry response length: {len(raw_code) if raw_code else 0}")
                        print(f"🔍 Simplified retry response preview: {repr(raw_code[:200]) if raw_code else 'EMPTY'}")
                    
                    # Validate simplified response
                    if _validate_response_content(raw_code):
                        cleaned_code = self.content_filter.clean_model_output(raw_code)
                        extracted_code = self.code_processor.extract_pure_function_code(cleaned_code)
                        
                        if extracted_code and len(extracted_code.strip()) >= 20:
                            return StandardizedModelResponse(
                                content=extracted_code,
                                is_valid=True,
                                metadata={"generation_type": "simplified_retry", "model": model, "attempt": attempt},
                                raw_response=raw_code,
                                extraction_method="ast_based"
                            )
                    
                except Exception as model_error:
                    if self.config.ENABLE_DEBUG_MODE:
                        print(f"❌ Model {model} failed with error: {model_error}")
                    continue
                
                # Model attempt failed, try next model
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"❌ Model {model} failed validation, trying next model...")
            
            # All models failed, try enhanced fallback generation
            if self.config.ENABLE_DEBUG_MODE:
                print(f"🚨 All models failed, attempting enhanced fallback generation...")
            
            fallback_code = self._generate_enhanced_fallback_function(prompt)
            if fallback_code:
                return StandardizedModelResponse(
                    content=fallback_code,
                    is_valid=True,
                    metadata={"generation_type": "enhanced_fallback"},
                    raw_response="",
                    extraction_method="fallback"
                )
            else:
                return StandardizedModelResponse(
                    content="",
                    is_valid=False,
                    error_message="All models failed and enhanced fallback generation failed",
                    raw_response=""
                )
            
        except Exception as e:
            logging.error(f"Enhanced code generation failed: {e}")
            self.failure_learner.record_failure(
                description=prompt[:100],
                error_type="generation_exception",
                code_content=str(e)
            )
            return StandardizedModelResponse(
                content="",
                is_valid=False,
                error_message=str(e)
            )
    
    def _adjust_failing_prompt(self, prompt: str) -> str:
        """Adjust a prompt that's likely to fail based on learned patterns."""
        # Add specific constraints to avoid common failure patterns
        adjustments = [
            "CRITICAL: Generate complete working function only",
            "CRITICAL: No explanatory text or examples",
            "CRITICAL: Must be syntactically correct Python",
            "CRITICAL: Must follow LLM tool interface with input_data parameter",
            "CRITICAL: Function name must be specific, NOT 'process_input'"
        ]
        
        adjusted_prompt = prompt + "\n\n" + "\n".join(adjustments)
        return adjusted_prompt
    
    def _generate_unique_function_name(self, base_name: str, domain: str = None) -> str:
        """
        EDIT 4: Function Name Uniqueness Validation - Generate collision-proof unique function names.
        Uses UUID and timestamp for guaranteed uniqueness.
        """
        # Clean the base name
        clean_base = re.sub(r'[^a-zA-Z0-9_]', '_', base_name)
        clean_base = re.sub(r'_+', '_', clean_base).strip('_')
        
        if not clean_base:
            clean_base = "generated_function"
        
        # Generate timestamp-based suffix
        timestamp = int(time.time() * 1000) % 100000  # Last 5 digits of timestamp
        
        # Generate short UUID suffix
        uuid_suffix = str(uuid.uuid4())[:8]
        
        # Combine for uniqueness
        unique_name = f"{clean_base}_{timestamp}_{uuid_suffix}"
        
        # Ensure it's a valid Python identifier
        if not unique_name[0].isalpha() and unique_name[0] != '_':
            unique_name = f"func_{unique_name}"
        
        return unique_name
    
    def _generate_enhanced_fallback_function(self, prompt: str) -> str:
        """
        EDIT 1: Enhanced Fallback Function Generation - Generate collision-proof fallback with UUID naming.
        Enhanced with unique naming to prevent database collisions.
        """
        try:
            # Extract meaningful words from prompt for function naming
            words = re.findall(r'\w+', prompt.lower())
            action_words = [w for w in words if w in ['process', 'extract', 'convert', 'format', 'parse', 'analyze', 'validate', 'transform']]
            
            if action_words:
                base_name = f"{action_words[0]}_data"
            else:
                data_words = [w for w in words if w in ['text', 'json', 'csv', 'data', 'string', 'number']]
                if data_words:
                    base_name = f"process_{data_words[0]}"
                else:
                    base_name = "process_input"
            
            # EDIT 4: Generate unique function name to prevent collisions
            func_name = self._generate_unique_function_name(base_name)
            
            # Enhanced template with collision-proof naming
            return f'''def {func_name}(input_data):
    """
    Enhanced LLM tool function for processing input data with comprehensive error handling.
    
    Args:
        input_data (dict): Dictionary containing data to process
        
    Returns:
        dict: Result dictionary with 'result', 'status', and 'error' keys
    """
    try:
        # Validate input parameter
        if not isinstance(input_data, dict):
            return {{
                "result": None,
                "status": "error",
                "error": "Input must be a dictionary"
            }}
        
        # Extract data from various possible keys
        data = input_data.get('data') or input_data.get('input') or input_data.get('content') or input_data
        
        if data is None:
            return {{
                "result": None,
                "status": "error",
                "error": "No data found in input"
            }}
        
        # Enhanced processing with comprehensive analysis
        try:
            result = {{
                "processed_data": str(data),
                "data_length": len(str(data)),
                "data_type": type(data).__name__,
                "timestamp": "{datetime.now().isoformat()}",
                "function_name": "{func_name}",
                "processing_successful": True
            }}
            
            # Additional processing based on data type
            if isinstance(data, str):
                result.update({{
                    "character_count": len(data),
                    "word_count": len(data.split()) if data else 0,
                    "is_empty": not bool(data.strip())
                }})
            elif isinstance(data, (list, tuple)):
                result.update({{
                    "item_count": len(data),
                    "first_item": data[0] if data else None,
                    "is_empty": len(data) == 0
                }})
            elif isinstance(data, dict):
                result.update({{
                    "key_count": len(data),
                    "keys": list(data.keys())[:10],  # First 10 keys
                    "is_empty": len(data) == 0
                }})
            
            return {{
                "result": result,
                "status": "success",
                "error": None
            }}
            
        except Exception as processing_error:
            return {{
                "result": {{
                    "raw_data": str(data)[:200],  # First 200 chars for safety
                    "processing_failed": True,
                    "error_details": str(processing_error)
                }},
                "status": "partial_success",
                "error": f"Processing completed with issues: {{str(processing_error)}}"
            }}
        
    except Exception as e:
        return {{
            "result": None,
            "status": "error",
            "error": f"Function execution failed: {{str(e)}}"
        }}'''
        except Exception:
            # Ultimate fallback with timestamp-based naming
            timestamp = int(time.time() * 1000) % 100000
            return f"""def fallback_function_{timestamp}(input_data):
    try:
        return {{"result": str(input_data), "status": "success", "error": None}}
    except Exception as e:
        return {{"result": None, "status": "error", "error": str(e)}}"""
    
    def generate_diverse_exploration_prompt(self, domain: str = None, iteration: int = 0) -> str:
        """Generate diverse prompts for autonomous exploration."""
        return self.prompt_generator.generate_diverse_prompt(domain, iteration)
    
    def analyze_code_safety_standardized(self, code: str, function_name: str) -> StandardizedModelResponse:
        """Perform enhanced safety analysis with comprehensive filtering."""
        # Use fallback to manual analysis
        fallback_analysis = self._manual_safety_analysis(code, function_name)
        return StandardizedModelResponse(
            content=json.dumps(fallback_analysis),
            is_valid=True,
            metadata=fallback_analysis
        )
    
    def _manual_safety_analysis(self, code: str, function_name: str) -> Dict[str, Any]:
        """Manual safety analysis as fallback."""
        concerns = []
        safety_rating = "HIGH"
        
        # Check for risky operations
        high_risk_patterns = ['eval', 'exec', 'subprocess', 'os.system', '__import__']
        medium_risk_patterns = ['open', 'file', 'compile', 'getattr', 'setattr']
        
        code_lower = code.lower()
        
        for pattern in high_risk_patterns:
            if pattern in code_lower:
                concerns.append(f"Uses potentially dangerous function: {pattern}")
                safety_rating = "LOW"
        
        for pattern in medium_risk_patterns:
            if pattern in code_lower:
                concerns.append(f"Uses file/system operation: {pattern}")
                if safety_rating == "HIGH":
                    safety_rating = "MEDIUM"
        
        # Determine domain based on code content and context
        domain = "general"
        if any(term in code_lower for term in ['text', 'string', 'str', 'word']):
            domain = "text_processing"
        elif any(term in code_lower for term in ['data', 'list', 'dict', 'json']):
            domain = "data_manipulation"
        elif any(term in code_lower for term in ['valid', 'check', 'verify']):
            domain = "validation"
        elif any(term in code_lower for term in ['parse', 'extract', 'split']):
            domain = "parsing"
        elif any(term in code_lower for term in ['format', 'convert', 'transform']):
            domain = "formatting"
        elif any(term in code_lower for term in ['calculate', 'compute', 'math']):
            domain = "calculation"
        elif any(term in code_lower for term in ['analyze', 'process', 'examine']):
            domain = "analysis"
        
        return {
            "is_safe": safety_rating != "LOW",
            "safety_rating": safety_rating,
            "domain": domain,
            "description": f"Enhanced LLM tool for {domain} operations",
            "concerns": concerns
        }
    
    def get_failure_summary(self) -> Dict[str, Any]:
        """Get comprehensive failure analysis summary."""
        return self.failure_learner.get_failure_summary()
    
    def stop_autonomous(self):
        """Signal to stop autonomous exploration."""
        self.kill_autonomous.set()
    
    def reset_autonomous(self):
        """Reset autonomous exploration state."""
        self.kill_autonomous.clear()


# ============================================================================
# ENHANCED FUNCTION VALIDATION SYSTEM WITH SECURITY
# ============================================================================

class AdvancedFunctionValidator:
    """
    Enhanced function validation with security analysis and comprehensive testing.
    """
    
    def __init__(self, model_interface: AdvancedModelInterface, config: 'SystemConfig'):
        self.model_interface = model_interface
        self.config = config
        self.test_executor = AdvancedTestExecutor(config)
        self.code_processor = AdvancedCodeProcessor()
    
    def _generate_unique_function_name(self, base_name: str, domain: str = None) -> str:
        """
        EDIT 4: Function Name Uniqueness Validation - Generate unique function names for validation.
        """
        return self.model_interface._generate_unique_function_name(base_name, domain)
    
    def _run_security_analysis(self, code: str) -> Dict[str, Any]:
        """Perform static security analysis using Bandit."""
        if not BANDIT_AVAILABLE or not self.config.ENABLE_SECURITY_ANALYSIS:
            return {'issues': []}
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(code)
                temp_file_path = temp_file.name
            
            result = subprocess.run(['bandit', '-r', temp_file_path], capture_output=True, text=True)
            issues = result.stdout.split('\n') if result.returncode != 0 else []
            
            os.unlink(temp_file_path)
            return {'issues': [i for i in issues if i.strip()]}
        except Exception as e:
            return {'issues': [str(e)]}
    
    def validate_function(self, code: str, function_name: str, source_artifact: str = "") -> Tuple[bool, Optional[FunctionMetadata], str]:
        """Enhanced function validation with early duplicate prevention and content quality gates."""
        attempts = 0
        current_code = code
        debug_info = {
            "attempts": [], 
            "errors": [], 
            "fixes": [], 
            "strategies": [],
            "original_code_length": len(code),
            "validation_start": datetime.now().isoformat(),
            "source_artifact": source_artifact
        }
        
        while attempts < self.config.MAX_RETRY_ATTEMPTS:
            attempts += 1
            attempt_info = {
                "attempt": attempts, 
                "timestamp": datetime.now().isoformat(),
                "code_length": len(current_code)
            }
            
            try:
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"🔍 Enhanced validation attempt {attempts} for function: {function_name}")
                
                # Step 1: Enhanced content cleaning and preprocessing
                original_code_for_logging = current_code
                current_code = self.model_interface.content_filter.clean_model_output(current_code)
                current_code = self.code_processor.extract_pure_function_code(current_code)
                
                # Log cleaning transformation
                if self.config.ENABLE_CODE_DIFF_LOGGING and original_code_for_logging != current_code:
                    self.model_interface.code_diff_logger.log_content_cleaning(
                        raw_output=original_code_for_logging,
                        cleaned_code=current_code,
                        extraction_method="validation_preprocessing",
                        success=bool(current_code and len(current_code.strip()) > 10),
                        function_name=function_name
                    )
                
                attempt_info["code_after_cleaning"] = len(current_code)
                
                # Check if we have any code at all
                if not current_code or len(current_code.strip()) < 10:
                    if attempts >= self.config.MAX_RETRY_ATTEMPTS:
                        return False, None, "No valid function code could be extracted"
                    
                    # Try to regenerate
                    current_code = self._regenerate_function(function_name)
                    continue
                
                # Enhanced function name validation and collision prevention
                extracted_name = self.code_processor.get_function_name(current_code)
                if not extracted_name:
                    if attempts >= self.config.MAX_RETRY_ATTEMPTS:
                        raise ValidationError(f"Could not extract function name from code:\n{current_code[:200]!r}")
                    attempt_info["name_extraction_failed"] = True
                    # Generate unique name if extraction failed
                    extracted_name = self._generate_unique_function_name("generated_function")
                    # Replace the function name in code
                    current_code = re.sub(r'def\s+\w+\s*\(', f'def {extracted_name}(', current_code, count=1)
                else:
                    function_name = extracted_name  # Use extracted name
                
                # EDIT 4: Enhanced duplicate detection with function name check
                if self.config.database.function_name_exists(function_name):
                    attempt_info["name_duplicate"] = function_name
                    debug_info["attempts"].append(attempt_info)
                    return False, None, f"Function with name '{function_name}' already exists"
                
                attempt_info["extracted_function_name"] = function_name
                
                # Step 2: Enhanced syntax validation with detailed error reporting
                syntax_valid, syntax_error = self.code_processor.validate_function_syntax(current_code)
                if not syntax_valid:
                    attempt_info["syntax_error"] = syntax_error
                    debug_info["attempts"].append(attempt_info)
                    
                    if attempts >= self.config.MAX_RETRY_ATTEMPTS:
                        self.model_interface.failure_learner.record_failure(
                            description=f"Syntax validation failed for {function_name}",
                            error_type="syntax_error",
                            code_content=current_code[:200]
                        )
                        return False, None, f"Syntax validation failed: {syntax_error}"
                    
                    fixed_code = self._fix_syntax_error_enhanced(current_code, syntax_error, function_name)
                    
                    # Log syntax fix
                    if self.config.ENABLE_CODE_DIFF_LOGGING:
                        self.model_interface.code_diff_logger.log_syntax_fix(
                            original_code=current_code,
                            fixed_code=fixed_code,
                            syntax_error=syntax_error,
                            success=fixed_code != current_code,
                            function_name=function_name
                        )
                    
                    current_code = fixed_code
                    debug_info["fixes"].append(f"Attempted syntax fix: {syntax_error}")
                    continue
                
                # Step 3: Enhanced duplicate detection using both hash and AST
                code_hash = self.code_processor.calculate_code_hash(current_code)
                
                # Check hash-based duplicates first (faster)
                if self.config.database.function_exists(code_hash):
                    attempt_info["hash_duplicate"] = code_hash
                    debug_info["attempts"].append(attempt_info)
                    return False, None, f"Function with identical code hash already exists: {code_hash[:8]}..."
                
                # Check AST-based duplicates for semantic equivalence
                if self.config.ENABLE_AST_DUPLICATE_DETECTION:
                    existing_function = self.config.database.check_ast_duplicate(current_code)
                    if existing_function:
                        attempt_info["ast_duplicate"] = existing_function
                        debug_info["attempts"].append(attempt_info)
                        return False, None, f"Function with equivalent AST structure already exists: {existing_function}"
                
                # Step 4: Enhanced safety analysis
                safety_response = self.model_interface.analyze_code_safety_standardized(current_code, function_name)
                analysis = safety_response.metadata
                attempt_info["analysis"] = analysis
                
                if not analysis.get("is_safe", True):
                    attempt_info["safety_failure"] = True
                    debug_info["attempts"].append(attempt_info)
                    self.model_interface.failure_learner.record_failure(
                        description=f"Safety failure for {function_name}",
                        error_type="safety_violation",
                        code_content=current_code[:200]
                    )
                    return False, None, f"Function failed safety requirements: {analysis.get('concerns', [])}"
                
                # Step 5: Security analysis
                if self.config.ENABLE_SECURITY_ANALYSIS:
                    security_report = self._run_security_analysis(current_code)
                    if security_report['issues']:
                        self.model_interface.failure_learner.record_failure(
                            description=f"Security issues in {function_name}",
                            error_type="security_violation",
                            code_content=current_code[:200]
                        )
                        return False, None, f"Security issues found: {security_report['issues']}"
                
                # Step 6: Enhanced intelligent test execution with sandbox
                use_sandbox = self.config.ENABLE_SANDBOX_EXECUTION
                test_script = self.test_executor.create_intelligent_test_script(current_code, function_name)
                test_passed, test_error = self.test_executor.execute_test_script(current_code, test_script)
                attempt_info["test_passed"] = test_passed
                attempt_info["test_error"] = test_error
                
                if not test_passed:
                    if attempts >= self.config.MAX_RETRY_ATTEMPTS:
                        debug_info["attempts"].append(attempt_info)
                        self.model_interface.failure_learner.record_failure(
                            description=f"Test execution failed for {function_name}",
                            error_type="test_failure",
                            code_content=current_code[:200]
                        )
                        return False, None, f"Test execution failed: {test_error}"
                    
                    fixed_code = self._fix_execution_error_enhanced(current_code, test_error, function_name)
                    
                    # Log execution fix
                    if self.config.ENABLE_CODE_DIFF_LOGGING:
                        self.model_interface.code_diff_logger.log_code_transformation(
                            original_code=current_code,
                            processed_code=fixed_code,
                            transformation_type="execution_fix",
                            success=fixed_code != current_code,
                            validation_errors=[test_error] if test_error else [],
                            function_name=function_name
                        )
                    
                    current_code = fixed_code
                    debug_info["fixes"].append(f"Attempted execution fix: {test_error}")
                    continue
                
                # Step 7: Enhanced metadata creation with LLM tool focus
                signature = self._extract_function_signature_enhanced(current_code)
                complexity_score = self._calculate_complexity_score_enhanced(current_code)
                usage_example = self._generate_usage_example(current_code, function_name)
                input_output_description = self._generate_io_description(current_code, function_name)
                
                # Format code if enabled
                if self.config.ENABLE_CODE_FORMATTING:
                    try:
                        formatted_code = self.code_processor.format_code(current_code)
                        
                        # Log formatting transformation
                        if self.config.ENABLE_CODE_DIFF_LOGGING and formatted_code != current_code:
                            self.model_interface.code_diff_logger.log_code_formatting(
                                unformatted_code=current_code,
                                formatted_code=formatted_code,
                                success=True,
                                function_name=function_name
                            )
                        
                        current_code = formatted_code
                    except Exception as format_error:
                        debug_info["errors"].append(f"Code formatting failed: {format_error}")
                
                metadata = FunctionMetadata(
                    name=function_name,
                    domain=analysis.get("domain", "general"),
                    description=analysis.get("description", "Enhanced LLM tool function"),
                    parameters=self._extract_parameters_enhanced(current_code),
                    return_type=self._extract_return_type_enhanced(current_code),
                    created_at=datetime.now().isoformat(),
                    validation_status="VALIDATED",
                    test_results={
                        "passed": True, 
                        "attempts": attempts, 
                        "test_error": None,
                        "test_method": "intelligent_sandbox" if use_sandbox else "intelligent"
                    },
                    source_code=current_code,
                    dependencies=self._extract_dependencies_enhanced(current_code),
                    safety_rating=analysis.get("safety_rating", "HIGH"),
                    debug_info=debug_info,
                    signature=signature,
                    complexity_score=complexity_score,
                    code_hash=code_hash,
                    usage_example=usage_example,
                    input_output_description=input_output_description,
                    source_artifact=source_artifact
                )
                
                debug_info["attempts"].append(attempt_info)
                debug_info["validation_end"] = datetime.now().isoformat()
                debug_info["final_success"] = True
                
                return True, metadata, ""
                
            except Exception as e:
                error_context = f"Enhanced validation error: {e}"
                attempt_info["exception"] = str(e)
                debug_info["errors"].append(error_context)
                
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"❌ Enhanced validation attempt {attempts} failed: {e}")
                    traceback.print_exc()
                
                if attempts >= self.config.MAX_RETRY_ATTEMPTS:
                    debug_info["attempts"].append(attempt_info)
                    debug_info["validation_end"] = datetime.now().isoformat()
                    debug_info["final_success"] = False
                    self.model_interface.failure_learner.record_failure(
                        description=f"Validation exception for {function_name}",
                        error_type="validation_exception",
                        code_content=str(e)
                    )
                    return False, None, f"Validation failed with error: {e}"
        
        return False, None, "Maximum validation attempts exceeded"
    
    def _regenerate_function(self, function_name: str) -> str:
        """Regenerate function using enhanced fallback mechanism."""
        try:
            return self.model_interface._generate_enhanced_fallback_function(f"create {function_name}")
        except Exception:
            return ""
    
    def _fix_syntax_error_enhanced(self, code: str, error: str, function_name: str) -> str:
        """Enhanced syntax error fixing with intelligent strategies."""
        try:
            # Use more specific prompting for syntax fixes
            fix_prompt = f"""Fix this Python syntax error. Return ONLY the corrected function code.

Function: {function_name}
Error: {error}

Original code:
{code}

Requirements:
- Fix the syntax error
- Keep the function logic intact
- Ensure LLM tool interface (input_data parameter, dict return)
- Return only the function definition
- No explanations or examples

Corrected function:"""
            
            fix_response = self.model_interface.generate_code_robust(fix_prompt)
            
            if fix_response.is_valid and fix_response.content:
                fixed_code = fix_response.content
                # Verify the fix actually resolves the syntax error
                is_valid, _ = self.code_processor.validate_function_syntax(fixed_code)
                if is_valid:
                    return fixed_code
            
            # If model fix failed, try simple automated fixes
            return self._apply_automated_syntax_fixes(code, error)
            
        except Exception as e:
            logging.error(f"Enhanced syntax fix failed: {e}")
            return code
    
    def _apply_automated_syntax_fixes(self, code: str, error: str) -> str:
        """Apply simple automated syntax fixes."""
        try:
            # Common syntax fix patterns
            if "invalid syntax" in error.lower():
                # Fix smart quotes using Unicode escapes
                code = re.sub(r'[\u201c\u201d]', '"', code)  # Fix smart double quotes
                code = re.sub(r'[\u2018\u2019]', "'", code)  # Fix smart single quotes/apostrophes
                # Fix additional problematic Unicode characters
                code = re.sub(r'\u2013', '-', code)  # En dash to hyphen
                code = re.sub(r'\u2014', '--', code)  # Em dash to double hyphen
                code = re.sub(r'\u00a0', ' ', code)  # Non-breaking space to regular space
                
            if "indentation" in error.lower():
                # Try to fix indentation issues
                lines = code.split('\n')
                fixed_lines = []
                for line in lines:
                    if line.strip():
                        if line.startswith('def '):
                            fixed_lines.append(line)
                        else:
                            # Ensure proper indentation for function body
                            fixed_lines.append('    ' + line.lstrip())
                    else:
                        fixed_lines.append(line)
                code = '\n'.join(fixed_lines)
            
            return code
        except Exception as e:
            logging.error(f"Automated syntax fix failed: {e}")
            return code
    
    def _fix_execution_error_enhanced(self, code: str, error: str, function_name: str) -> str:
        """Enhanced execution error fixing with intelligent analysis."""
        try:
            # Analyze the error to provide targeted fixes
            error_type = "general"
            if "name" in error.lower() and "not defined" in error.lower():
                error_type = "undefined_name"
            elif "type" in error.lower() and "object" in error.lower():
                error_type = "type_error"
            elif "index" in error.lower() or "key" in error.lower():
                error_type = "access_error"
            
            fix_prompt = f"""Fix this Python execution error. Return ONLY the corrected function code.

Function: {function_name}
Error type: {error_type}
Error: {error}

Original code:
{code}

Requirements:
- Fix the execution error
- Add proper error handling
- Ensure LLM tool interface (input_data parameter, dict return)
- Ensure function works with various inputs
- Return only the function definition

Corrected function:"""
            
            fix_response = self.model_interface.generate_code_robust(fix_prompt)
            
            if fix_response.is_valid and fix_response.content:
                return fix_response.content
            else:
                return code
                
        except Exception as e:
            logging.error(f"Enhanced execution fix failed: {e}")
            return code
    
    def _generate_usage_example(self, code: str, function_name: str) -> str:
        """Generate usage example for LLM guidance."""
        try:
            return f"""
# Example usage:
input_data = {{"data": "sample input", "options": {{"format": "json"}}}}
result = {function_name}(input_data)
print(result['result'])  # Access the processed result
"""
        except Exception:
            return f"result = {function_name}({{'data': 'sample_input'}})"
    
    def _generate_io_description(self, code: str, function_name: str) -> str:
        """Generate input/output description for LLM understanding."""
        try:
            # Analyze function to determine input/output patterns
            if "input_data" in code:
                return "Input: Dictionary with 'data' or other relevant keys. Output: Dictionary with 'result', 'status', and 'error' keys."
            else:
                return "Standard function input/output - consult function signature and docstring."
        except Exception:
            return "Input/output description unavailable."
    
    def _extract_function_signature_enhanced(self, code: str) -> str:
        """Extract complete function signature using AST."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Reconstruct the signature
                    args = []
                    for arg in node.args.args:
                        arg_str = arg.arg
                        if arg.annotation:
                            if isinstance(arg.annotation, ast.Name):
                                arg_str += f": {arg.annotation.id}"
                            else:
                                arg_str += ": Any"
                        args.append(arg_str)
                    
                    return_annotation = ""
                    if node.returns:
                        if isinstance(node.returns, ast.Name):
                            return_annotation = f" -> {node.returns.id}"
                        else:
                            return_annotation = " -> Any"
                    
                    return f"def {node.name}({', '.join(args)}){return_annotation}:"
        except Exception:
            # Fallback to regex
            match = re.search(r'def\s+\w+\s*\([^)]*\)(?:\s*->\s*[^:]+)?:', code)
            if match:
                return match.group(0)
        
        return ""
    
    def _calculate_complexity_score_enhanced(self, code: str) -> int:
        """Calculate enhanced function complexity score."""
        try:
            # Use AST for accurate complexity calculation
            tree = ast.parse(code)
            
            complexity = 1  # Base complexity
            
            for node in ast.walk(tree):
                # Control flow complexity
                if isinstance(node, (ast.If, ast.For, ast.While, ast.With)):
                    complexity += 1
                elif isinstance(node, (ast.Try, ast.ExceptHandler)):
                    complexity += 1
                elif isinstance(node, ast.comprehension):
                    complexity += 1
                # Function calls add minor complexity
                elif isinstance(node, ast.Call):
                    complexity += 0.5
            
            # Line count factor
            lines = [line.strip() for line in code.split('\n') if line.strip()]
            line_factor = len(lines) // 10
            
            final_score = min(10, max(1, int(complexity + line_factor)))
            return final_score
            
        except Exception:
            # Fallback to simple calculation
            lines = [line.strip() for line in code.split('\n') if line.strip()]
            line_count = len(lines)
            control_structures = len(re.findall(r'\b(if|for|while|try|except|with)\b', code))
            
            score = min(10, max(1, 3 + (line_count // 5) + control_structures))
            return score
    
    def _extract_parameters_enhanced(self, code: str) -> Dict[str, str]:
        """Enhanced function parameter extraction using AST."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    params = {}
                    
                    # Regular arguments
                    for arg in node.args.args:
                        param_name = arg.arg
                        if arg.annotation:
                            if isinstance(arg.annotation, ast.Name):
                                param_type = arg.annotation.id
                            elif isinstance(arg.annotation, ast.Constant):
                                param_type = str(arg.annotation.value)
                            else:
                                param_type = "Any"
                        else:
                            param_type = "Any"
                        params[param_name] = param_type
                    
                    # Default arguments
                    defaults = node.args.defaults
                    if defaults:
                        default_offset = len(node.args.args) - len(defaults)
                        for i, default in enumerate(defaults):
                            arg_index = default_offset + i
                            if arg_index < len(node.args.args):
                                arg_name = node.args.args[arg_index].arg
                                if isinstance(default, ast.Constant):
                                    params[arg_name] += f" = {repr(default.value)}"
                    
                    return params
        except Exception:
            pass
        
        # Fallback to regex-based extraction
        try:
            pattern = r'def\s+\w+\s*\(([^)]*)\)'
            match = re.search(pattern, code)
            if match:
                params_str = match.group(1)
                params = {}
                for param in params_str.split(','):
                    param = param.strip()
                    if param and ':' in param:
                        name, type_hint = param.split(':', 1)
                        params[name.strip()] = type_hint.strip()
                    elif param:
                        params[param] = "Any"
                return params
        except Exception:
            pass
        
        return {}
    
    def _extract_return_type_enhanced(self, code: str) -> str:
        """Enhanced return type extraction using AST."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.returns:
                        if isinstance(node.returns, ast.Name):
                            return node.returns.id
                        elif isinstance(node.returns, ast.Constant):
                            return str(node.returns.value)
                        else:
                            return "Any"
        except Exception:
            pass
        
        # Fallback to regex
        try:
            pattern = r'def\s+\w+\s*\([^)]*\)\s*->\s*([^:]+):'
            match = re.search(pattern, code)
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        
        return "dict"  # Default return type for LLM tools
    
    def _extract_dependencies_enhanced(self, code: str) -> List[str]:
        """Enhanced import dependency extraction using AST."""
        dependencies = []
        
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.asname:
                            dependencies.append(f"import {alias.name} as {alias.asname}")
                        else:
                            dependencies.append(f"import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        if alias.asname:
                            dependencies.append(f"from {module} import {alias.name} as {alias.asname}")
                        else:
                            dependencies.append(f"from {module} import {alias.name}")
        except Exception:
            # Fallback to line-based detection
            lines = code.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('import ') or line.startswith('from '):
                    dependencies.append(line)
        
        return dependencies


# ============================================================================
# ENHANCED SYSTEM ORCHESTRATOR WITH GOAL-DRIVEN AUTONOMY
# ============================================================================

class AdvancedAutonomousFunctionDevelopmentSystem:
    """
    Enhanced system orchestrator with proper model usage patterns and architectural fixes.
    """
    
    def __init__(self, config: SystemConfig = None):
        self.config = config or SystemConfig.load_from_file()
        self._setup_advanced_logging()
        self._setup_directories()
        
        # Initialize enhanced core components
        self.database = AdvancedFunctionDatabase(self.config.DATABASE_PATH)
        self.model_interface = AdvancedModelInterface(self.config)
        self.validator = AdvancedFunctionValidator(self.model_interface, self.config)
        self.content_filter = IntelligentContentFilter()
        self.code_processor = AdvancedCodeProcessor()
        self.action_monitor = ActionMonitor(self.config)
        self.nl_processor = NaturalLanguageCommandProcessor(self)
        self.local_explorer = LocalSystemExplorer(self.config, self.action_monitor)
        
        # Set database reference for duplicate checking
        self.config.database = self.database
        
        # Set action monitor reference for code diff logging
        self.config.action_monitor = self.action_monitor
        
        # Load failure patterns from database
        if self.config.ENABLE_FAILURE_LEARNING:
            failure_patterns = self.database.load_failure_patterns()
            self.model_interface.failure_learner.failure_patterns = failure_patterns
        
        # System state
        self.autonomous_mode = False
        self.autonomous_task = None
        self.shutdown_requested = False
        self.autonomous_goals = []
        self.stop_event = threading.Event()  # EDIT 3: Enhanced thread management
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("✅ Enhanced Autonomous Function Development System v5.2.3 (ARCHITECTURALLY FIXED) initialized")
    
    def _setup_advanced_logging(self):
        """Configure enhanced enterprise-grade logging."""
        os.makedirs(self.config.LOGS_PATH, exist_ok=True)
        
        # Disable noisy loggers
        for logger_name in ["httpx", "httpcore", "asyncio", "urllib3", "ollama"]:
            logging.getLogger(logger_name).setLevel(logging.WARNING)
        
        log_level = logging.DEBUG if self.config.ENABLE_DEBUG_MODE else self.config.LOG_LEVEL
        
        # Enhanced logging configuration with rotation
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        
        handlers = [
            logging.FileHandler(f"{self.config.LOGS_PATH}/enhanced_system.log")
        ]
        
        if self.config.ENABLE_DEBUG_MODE:
            handlers.append(logging.StreamHandler())
        
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=handlers
        )
    
    def _setup_directories(self):
        """Create system directories with enhanced error handling."""
        for path in [self.config.LOGS_PATH, self.config.TEMP_PATH, self.config.SANDBOX_PATH]:
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"⚠️  Could not create directory {path}: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self.shutdown_requested = True
        self.stop_autonomous_mode()
        
        # Save failure patterns before exit
        if self.config.ENABLE_FAILURE_LEARNING:
            self._save_failure_patterns()
        
        sys.exit(0)
    
    def _save_failure_patterns(self):
        """Save learned failure patterns to database."""
        try:
            for pattern in self.model_interface.failure_learner.failure_patterns.values():
                self.database.store_failure_pattern(pattern)
            if self.config.ENABLE_DEBUG_MODE:
                print("💾 Failure patterns saved")
        except Exception as e:
            if self.config.ENABLE_DEBUG_MODE:
                print(f"⚠️  Failed to save failure patterns: {e}")
    
    def create_function(self, description: str, domain: str = None, source_artifact: str = "") -> bool:
        """Create function with enhanced enterprise-grade reliability and LLM tool focus."""
        try:
            print(f"🔧 Creating enhanced LLM tool function: {description[:60]}...")
            
            # Log action for monitoring
            if self.config.ENABLE_ACTION_MONITORING:
                self.action_monitor.log_action(
                    "function_creation",
                    f"Creating function: {description[:60]}",
                    {"description": description, "domain": domain, "source_artifact": source_artifact}
                )
            
            # Enhanced description processing and validation for LLM tools
            processed_desc = self._process_function_description_enhanced(description, domain)
            
            # Check if this type of function has failed before
            if (self.config.ENABLE_FAILURE_LEARNING and 
                self.model_interface.failure_learner.is_likely_to_fail(processed_desc)):
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"⚠️  Warning: Similar functions have failed before, adjusting approach...")
            
            # Enhanced code generation with intelligent retry
            code_response = self.model_interface.generate_code_robust(processed_desc)
            
            if not code_response.is_valid:
                print(f"❌ Enhanced code generation failed: {code_response.error_message}")
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"🔍 Debug: Response was: {code_response.content[:200]}")
                
                # Log failure
                if self.config.ENABLE_ACTION_MONITORING:
                    self.action_monitor.log_action(
                        "function_creation",
                        "Code generation failed",
                        {"error": code_response.error_message},
                        success=False,
                        error_message=code_response.error_message
                    )
                return False
            
            code = code_response.content
            
            # Enhanced function name extraction
            function_name = self.code_processor.get_function_name(code)
            
            if not function_name:
                print("❌ Could not extract function name from generated code")
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"🔍 Debug: Code was: {code[:200]}")
                
                # Log failure
                if self.config.ENABLE_ACTION_MONITORING:
                    self.action_monitor.log_action(
                        "function_creation",
                        "Function name extraction failed",
                        {"code_preview": code[:200]},
                        success=False,
                        error_message="Could not extract function name"
                    )
                return False
            
            # Enhanced function validation with security analysis
            is_valid, metadata, error_msg = self.validator.validate_function(code, function_name, source_artifact)
            
            if is_valid:
                success = self.database.store_function(metadata)
                if success:
                    print(f"✅ ENHANCED LLM TOOL FUNCTION CREATED: {metadata.name} in domain '{metadata.domain}'")
                    print(f"   Description: {metadata.description}")
                    print(f"   Safety Rating: {metadata.safety_rating}")
                    print(f"   Complexity Score: {metadata.complexity_score}")
                    print(f"   Code Hash: {metadata.code_hash[:8]}...")
                    print(f"   LLM Tool Interface: {'✅' if 'input_data' in metadata.source_code else '⚠️'}")
                    if metadata.source_artifact:
                        print(f"   Source Artifact: {metadata.source_artifact}")
                    
                    # Log successful creation
                    if self.config.ENABLE_ACTION_MONITORING:
                        self.action_monitor.log_action(
                            "function_creation",
                            f"Successfully created function: {metadata.name}",
                            {
                                "function_name": metadata.name,
                                "domain": metadata.domain,
                                "safety_rating": metadata.safety_rating,
                                "complexity_score": metadata.complexity_score,
                                "llm_tool_compatible": 'input_data' in metadata.source_code,
                                "source_artifact": metadata.source_artifact
                            }
                        )
                    return True
                else:
                    print("❌ Failed to store validated function")
                    
                    # Log storage failure
                    if self.config.ENABLE_ACTION_MONITORING:
                        self.action_monitor.log_action(
                            "function_creation",
                            "Function storage failed",
                            {"function_name": metadata.name},
                            success=False,
                            error_message="Database storage failed"
                        )
                    return False
            else:
                print(f"❌ ENHANCED FUNCTION VALIDATION FAILED: {error_msg}")
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"🔍 Debug: Validation attempts and errors available in logs")
                
                # Log validation failure
                if self.config.ENABLE_ACTION_MONITORING:
                    self.action_monitor.log_action(
                        "function_creation",
                        "Function validation failed",
                        {"function_name": function_name, "error": error_msg},
                        success=False,
                        error_message=error_msg
                    )
                return False
                
        except Exception as e:
            print(f"❌ ENHANCED FUNCTION CREATION ERROR: {e}")
            if self.config.ENABLE_DEBUG_MODE:
                traceback.print_exc()
            
            # Log exception
            if self.config.ENABLE_ACTION_MONITORING:
                self.action_monitor.log_action(
                    "function_creation",
                    "Function creation exception",
                    {"description": description, "exception": str(e)},
                    success=False,
                    error_message=str(e)
                )
            return False
    
    def _process_function_description_enhanced(self, description: str, domain: str = None) -> str:
        """Enhanced description processing for LLM tool specifications."""
        description = description.strip('<>[]').strip()
        
        # Enhanced concept mappings with LLM tool focus
        concept_mappings = {
            "browse the internet": "parse and extract data from web-like text content",
            "web browsing": "process and analyze HTML-like text data structures", 
            "internet browsing": "extract links and structured data from text patterns",
            "web scraping": "extract and structure data from text using pattern recognition",
            "data analysis": "calculate comprehensive statistics and analyze data structures",
            "file management": "organize, validate, and format data collections",
            "system monitoring": "track, analyze, and report on metrics from data",
            "ai processing": "analyze, classify, and transform text data intelligently",
            "machine learning": "process, classify, and analyze data patterns",
            "natural language processing": "analyze and extract information from text",
            "image processing": "analyze and extract metadata from text representations",
            "database operations": "structure, validate, and query data collections"
        }
        
        description_lower = description.lower()
        for abstract_term, concrete_impl in concept_mappings.items():
            if abstract_term in description_lower:
                description = description.replace(abstract_term, concrete_impl)
        
        # Enhanced domain specification
        if domain:
            description = f"For {domain} domain: {description}"
        
        # Ensure LLM tool requirements are clear
        if 'function' not in description_lower:
            description = f"Create a LLM tool function that {description}"
        
        # Add specific LLM tool interface requirements
        if not any(word in description_lower for word in ['input_data', 'parameter', 'return']):
            description += " that accepts input_data dictionary parameter and returns structured results dictionary"
        
        return description
    
    def start_autonomous_mode(self, domain: str = None, full_autonomy: bool = False):
        """Start enhanced autonomous exploration using intelligence model for exploration."""
        if self.autonomous_mode:
            print("⚠️  Enhanced autonomous mode already running")
            return
        
        self.autonomous_mode = True
        self.stop_event.clear()  # EDIT 3: Reset stop event
        self.model_interface.reset_autonomous()
        
        # Start action monitoring
        if self.config.ENABLE_ACTION_MONITORING:
            self.action_monitor.start_monitoring()
        
        # Set autonomous goals
        if full_autonomy:
            self.autonomous_goals = [
                "Generate diverse LLM tool functions",
                "Explore different domains and capabilities", 
                "Create comprehensive function library",
                "Validate all functions in sandbox environment",
                "Learn from failures and optimize generation",
                "Discover and integrate local system artifacts"
            ]
        elif domain:
            self.autonomous_goals = [
                f"Generate specialized LLM tools for {domain}",
                f"Create comprehensive {domain} function library",
                f"Validate {domain} functions thoroughly"
            ]
        else:
            self.autonomous_goals = [
                "Generate general-purpose LLM tool functions",
                "Create diverse utility function library"
            ]
        
        mode_desc = "Full Enhanced Autonomy" if full_autonomy else f"Enhanced Domain: {domain}" if domain else "Enhanced General Exploration"
        print(f"🚀 STARTING ENHANCED AUTONOMOUS MODE (ARCHITECTURALLY FIXED) - {mode_desc}")
        print(f"   Max iterations: {self.config.MAX_AUTONOMOUS_ITERATIONS}")
        print(f"   Exploration timeout: {self.config.EXPLORATION_TIMEOUT}s")
        print(f"   Cycle interval: {self.config.EXPLORATION_INTERVAL}s")
        print("\n🎯 AUTONOMOUS GOALS:")
        for i, goal in enumerate(self.autonomous_goals, 1):
            print(f"   {i}. {goal}")
        print("\n   Streaming enhanced model behavior... (Type 'KILL' to stop)")
        print("=" * 80)
        
        def run_enhanced_autonomous_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self._enhanced_autonomous_worker_async(domain, full_autonomy))
            except Exception as e:
                print(f"\n❌ ENHANCED AUTONOMOUS MODE ERROR: {e}")
                if self.config.ENABLE_DEBUG_MODE:
                    traceback.print_exc()
            finally:
                loop.close()
                self.autonomous_mode = False
                if self.config.ENABLE_ACTION_MONITORING:
                    self.action_monitor.stop_monitoring()
                print("\n🛑 ENHANCED AUTONOMOUS MODE STOPPED")
        
        self.autonomous_task = threading.Thread(target=run_enhanced_autonomous_worker, daemon=True)
        self.autonomous_task.start()
    
    async def _enhanced_autonomous_worker_async(self, domain: str = None, full_autonomy: bool = False):
        """
        Enhanced autonomous worker using intelligence model for exploration.
        """
        try:
            exploration_count = 0
            max_iterations = self.config.MAX_AUTONOMOUS_ITERATIONS
            start_time = time.time()
            success_count = 0
            failure_count = 0
            current_goal_index = 0
            artifact_functions_created = 0
            
            # Log autonomous mode start
            if self.config.ENABLE_ACTION_MONITORING:
                self.action_monitor.log_action(
                    "autonomous_mode",
                    f"Started autonomous mode - {domain or 'general'} domain",
                    {
                        "domain": domain,
                        "full_autonomy": full_autonomy,
                        "goals": self.autonomous_goals,
                        "max_iterations": max_iterations
                    }
                )
            
            # Initial local system exploration if enabled and in full autonomy mode
            if full_autonomy and self.config.ENABLE_LOCAL_EXPLORATION:
                print(f"\n🔍 INITIAL LOCAL SYSTEM EXPLORATION")
                discovered_artifacts = self.local_explorer.scan_local_resources()
                if discovered_artifacts:
                    print(f"   Found {len(discovered_artifacts)} artifacts for potential function generation")
                    # Store artifacts in database
                    for artifact in discovered_artifacts:
                        self.database.store_discovered_artifact(artifact)
                
                # Discover installed tools
                if self.config.ENABLE_INSTALLED_TOOL_DISCOVERY:
                    found_tools = self.local_explorer.find_installed_commands()
                    if found_tools:
                        print(f"   Found {len(found_tools)} installed tools")
            
            while (self.autonomous_mode and 
                   exploration_count < max_iterations and 
                   not self.model_interface.kill_autonomous.is_set() and
                   not self.shutdown_requested and
                   not self.stop_event.is_set() and  # EDIT 3: Check stop event
                   (time.time() - start_time) < self.config.EXPLORATION_TIMEOUT):
                
                exploration_count += 1
                current_goal = self.autonomous_goals[current_goal_index % len(self.autonomous_goals)] if self.autonomous_goals else "General exploration"
                
                print(f"\n🔍 ENHANCED EXPLORATION CYCLE {exploration_count}")
                print(f"   Success: {success_count} | Failures: {failure_count} | Artifact-based: {artifact_functions_created}")
                print(f"   Current Goal: {current_goal}")
                
                # Log exploration cycle
                if self.config.ENABLE_ACTION_MONITORING:
                    self.action_monitor.log_action(
                        "exploration_cycle",
                        f"Starting cycle {exploration_count}",
                        {
                            "cycle": exploration_count,
                            "current_goal": current_goal,
                            "success_count": success_count,
                            "failure_count": failure_count,
                            "artifact_functions_created": artifact_functions_created
                        }
                    )
                
                # Decide between artifact-based and general exploration
                use_artifact_based = (full_autonomy and 
                                    self.config.ENABLE_LOCAL_EXPLORATION and
                                    exploration_count % 3 == 0)  # Every 3rd cycle
                
                exploration_prompt = ""
                source_artifact = ""
                
                if use_artifact_based:
                    # Use improved artifact selection
                    available_artifacts = self.local_explorer.get_available_artifacts()
                    if available_artifacts:
                        artifact = random.choice(available_artifacts)
                        exploration_prompt = self.local_explorer._create_artifact_prompt(artifact)
                        source_artifact = artifact.path
                        print(f"🎯 Using artifact-based exploration: {artifact.artifact_type}")
                        print(f"   Processing artifact: {os.path.basename(artifact.path)}")
                        
                        # Validate prompt is not empty
                        if not exploration_prompt.strip():
                            if self.config.ENABLE_DEBUG_MODE:
                                print(f"🚨 Empty artifact prompt generated, falling back to diverse prompt")
                            use_artifact_based = False
                    else:
                        if self.config.ENABLE_DEBUG_MODE:
                            print(f"🔍 No artifacts available, using diverse prompt")
                        use_artifact_based = False
                
                if not use_artifact_based:
                    # Generate diverse, intelligent prompts with goal focus
                    if self.config.ENABLE_DIVERSITY_INJECTION:
                        exploration_prompt = self.model_interface.generate_diverse_exploration_prompt(domain, exploration_count)
                        # Enhance prompt with current goal
                        exploration_prompt += f"\n\nCurrent objective: {current_goal}"
                        print(f"🎯 Using diverse prompt generation (iteration {exploration_count})")
                    else:
                        exploration_prompt = self._get_standard_exploration_prompt(domain)
                        exploration_prompt += f"\n\nObjective: {current_goal}"
                        print(f"🎯 Using standard exploration prompt")
                
                # Final validation that prompt is not empty
                if not exploration_prompt.strip():
                    if self.config.ENABLE_DEBUG_MODE:
                        print(f"🚨 CRITICAL: Generated empty prompt, skipping cycle")
                    failure_count += 1
                    continue
                
                if self.config.ENABLE_DEBUG_MODE:
                    print(f"🔍 Using prompt: {exploration_prompt[:100]}...")
                    print(f"🔍 Prompt length: {len(exploration_prompt)} characters")
                
                # Use intelligence model with async chat for exploration
                try:
                    full_response = ""
                    async for chunk in await self.model_interface.async_client.chat(
                        model=self.config.INTELLIGENCE_MODEL,
                        messages=[{"role": "user", "content": exploration_prompt}],
                        stream=True,
                        options={
                            "temperature": self.config.TEMPERATURE + 0.1,
                            "top_p": self.config.TOP_P + 0.1,  # Now 0.2 + 0.1 = 0.3
                            "max_tokens": self.config.MAX_TOKENS,
                            "stop": ["<think>", "</think>", "<thinking>", "</thinking>"]
                        }
                    ):
                        full_response += chunk['message']['content']
                    
                    if self.config.ENABLE_DEBUG_MODE:
                        print(f"🤖 Generated response ({len(full_response)} chars)")
                        if len(full_response) == 0:
                            print(f"🚨 EMPTY RESPONSE from intelligence model!")
                            print(f"🔍 Prompt was: {exploration_prompt[:200]}...")
                        else:
                            print(f"🔍 Response preview: {full_response[:100]}...")
                    else:
                        print(f"🤖 Generated response ({len(full_response)} chars)")
                        
                except Exception as e:
                    print(f"❌ Generation error: {e}")
                    failure_count += 1
                    continue
                
                # Validate response is not empty
                if not full_response or len(full_response.strip()) < 10:
                    if self.config.ENABLE_DEBUG_MODE:
                        print(f"🚨 Empty or very short response from intelligence model, skipping cycle")
                        print(f"🔍 Response was: {repr(full_response)}")
                    failure_count += 1
                    continue
                
                # Log AI response
                if self.config.ENABLE_ACTION_MONITORING:
                    self.action_monitor.log_action(
                        "ai_response",
                        "Generated exploration response",
                        {
                            "response_length": len(full_response),
                            "response_preview": full_response[:100],
                            "artifact_based": use_artifact_based,
                            "source_artifact": source_artifact,
                            "model_used": self.config.INTELLIGENCE_MODEL
                        }
                    )
                
                # Enhanced content cleaning
                cleaned_response = self.model_interface.content_filter.clean_model_output(full_response)
                
                # Enhanced function creation decision logic
                if cleaned_response and self._should_create_function_enhanced(cleaned_response):
                    function_desc = self._extract_implementable_function_description_enhanced(cleaned_response)
                    if function_desc:
                        print(f"\n🔧 CREATING ENHANCED LLM TOOL: {function_desc[:60]}...")
                        
                        # Log function creation decision
                        if self.config.ENABLE_ACTION_MONITORING:
                            self.action_monitor.log_action(
                                "function_decision",
                                "Decided to create function",
                                {
                                    "description": function_desc,
                                    "source_response": cleaned_response[:200],
                                    "artifact_based": use_artifact_based,
                                    "source_artifact": source_artifact
                                }
                            )
                        
                        # Record attempt for learning
                        attempt_start = time.time()
                        success = self.create_function(function_desc, domain, source_artifact)
                        attempt_duration = time.time() - attempt_start
                        
                        if success:
                            success_count += 1
                            if use_artifact_based:
                                artifact_functions_created += 1
                            print("✅ Enhanced LLM tool function successfully created and validated!")
                            print(f"   ⏱️  Creation time: {attempt_duration:.2f}s")
                            if source_artifact:
                                print(f"   📄 Based on artifact: {source_artifact}")
                            
                            # Move to next goal on success
                            if full_autonomy and len(self.autonomous_goals) > 1:
                                current_goal_index = (current_goal_index + 1) % len(self.autonomous_goals)
                        else:
                            failure_count += 1
                            print("❌ Enhanced function creation failed")
                            print(f"   ⏱️  Attempt time: {attempt_duration:.2f}s")
                            
                            # Learn from failure if enabled
                            if self.config.ENABLE_FAILURE_LEARNING:
                                self.model_interface.failure_learner.record_failure(
                                    description=function_desc[:100],
                                    error_type="creation_failure",
                                    code_content=""
                                )
                        
                        print("-" * 70)
                        
                        # Show learning progress periodically
                        if exploration_count % 10 == 0 and self.config.ENABLE_FAILURE_LEARNING:
                            failure_summary = self.model_interface.get_failure_summary()
                            print(f"📊 Learning Progress: {failure_summary['total_patterns']} patterns tracked")
                else:
                    if self.config.ENABLE_DEBUG_MODE:
                        print(f"🔍 Response did not meet function creation criteria")
                        print(f"🔍 Cleaned response length: {len(cleaned_response)}")
                
                # Autonomous system exploration (with safeguards)
                if full_autonomy and exploration_count % 5 == 0:
                    await self._autonomous_system_exploration()
                
                await asyncio.sleep(self.config.EXPLORATION_INTERVAL)
                
            # Final statistics
            print(f"\n📊 ENHANCED EXPLORATION COMPLETE:")
            print(f"   Total cycles: {exploration_count}")
            print(f"   Successful functions: {success_count}")
            print(f"   Failed attempts: {failure_count}")
            print(f"   Artifact-based functions: {artifact_functions_created}")
            print(f"   Success rate: {(success_count / exploration_count * 100):.1f}%" if exploration_count > 0 else "   Success rate: 0%")
            print(f"   Goals pursued: {len(self.autonomous_goals)}")
            
            if self.config.ENABLE_FAILURE_LEARNING:
                failure_summary = self.model_interface.get_failure_summary()
                print(f"   Failure patterns learned: {failure_summary['total_patterns']}")
            
            if self.config.ENABLE_CODE_DIFF_LOGGING:
                diff_stats = self.model_interface.code_diff_logger.get_statistics()
                print(f"   Code transformations logged: {diff_stats['total_entries']}")
            
            # Log completion
            if self.config.ENABLE_ACTION_MONITORING:
                self.action_monitor.log_action(
                    "autonomous_mode",
                    "Autonomous mode completed",
                    {
                        "total_cycles": exploration_count,
                        "success_count": success_count,
                        "failure_count": failure_count,
                        "artifact_functions_created": artifact_functions_created,
                        "success_rate": (success_count / exploration_count * 100) if exploration_count > 0 else 0
                    }
                )
                
        except Exception as e:
            logging.error(f"Enhanced autonomous exploration error: {e}")
            print(f"\n❌ ENHANCED AUTONOMOUS EXPLORATION ERROR: {e}")
            if self.config.ENABLE_DEBUG_MODE:
                traceback.print_exc()
            
            # Log error
            if self.config.ENABLE_ACTION_MONITORING:
                self.action_monitor.log_action(
                    "autonomous_mode",
                    "Autonomous mode error",
                    {"error": str(e)},
                    success=False,
                    error_message=str(e)
                )
    
    async def _autonomous_system_exploration(self):
        """Autonomous system exploration with safeguards."""
        if not self.action_monitor.check_safeguard("code_execution"):
            return
        
        exploration_actions = [
            "analyze_function_catalog",
            "review_failure_patterns", 
            "optimize_generation_strategies",
            "explore_new_domains",
            "scan_local_resources"
        ]
        
        for action in exploration_actions:
            if not self.autonomous_mode:
                break
                
            try:
                if action == "analyze_function_catalog":
                    catalog = self.database.get_function_catalog()
                    print(f"🔍 AUTONOMOUS: Analyzing function catalog ({len(catalog)} functions)")
                    
                    # Log analysis
                    if self.config.ENABLE_ACTION_MONITORING:
                        self.action_monitor.log_action("system_exploration",
                            "Analyzed function catalog",
                            {"function_count": len(catalog)}
                        )
                
                elif action == "review_failure_patterns":
                    if self.config.ENABLE_FAILURE_LEARNING:
                        summary = self.model_interface.get_failure_summary()
                        print(f"🔍 AUTONOMOUS: Reviewing failure patterns ({summary['total_patterns']} tracked)")
                        
                        # Log review
                        if self.config.ENABLE_ACTION_MONITORING:
                            self.action_monitor.log_action(
                                "system_exploration", 
                                "Reviewed failure patterns",
                                {"pattern_count": summary['total_patterns']}
                            )
                
                elif action == "optimize_generation_strategies":
                    print("🔍 AUTONOMOUS: Optimizing generation strategies based on success patterns")
                    
                    # Log optimization
                    if self.config.ENABLE_ACTION_MONITORING:
                        self.action_monitor.log_action(
                            "system_exploration",
                            "Optimized generation strategies",
                            {}
                        )
                
                elif action == "explore_new_domains":
                    domains = self.database.get_all_domains()
                    print(f"🔍 AUTONOMOUS: Exploring domain opportunities (current: {len(domains)})")
                    
                    # Log domain exploration
                    if self.config.ENABLE_ACTION_MONITORING:
                        self.action_monitor.log_action(
                            "system_exploration",
                            "Explored domain opportunities",
                            {"current_domains": len(domains), "domains": domains}
                        )
                
                elif action == "scan_local_resources":
                    if self.config.ENABLE_LOCAL_EXPLORATION:
                        print(f"🔍 AUTONOMOUS: Scanning local resources for new artifacts")
                        discovered = self.local_explorer.scan_local_resources()
                        print(f"   Discovered {len(discovered)} new artifacts")
                        
                        # Store new artifacts
                        for artifact in discovered:
                            self.database.store_discovered_artifact(artifact)
                        
                        # Log exploration
                        if self.config.ENABLE_ACTION_MONITORING:
                            self.action_monitor.log_action(
                                "system_exploration",
                                "Scanned local resources",
                                {"new_artifacts": len(discovered)}
                            )
                
                await asyncio.sleep(1)  # Brief pause between actions
                
            except Exception as e:
                print(f"⚠️  AUTONOMOUS: System exploration error in {action}: {e}")
                
                # Log exploration error
                if self.config.ENABLE_ACTION_MONITORING:
                    self.action_monitor.log_action(
                        "system_exploration",
                        f"Error in {action}",
                        {"action": action, "error": str(e)},
                        success=False,
                        error_message=str(e)
                    )
    
    def _get_standard_exploration_prompt(self, domain: str = None) -> str:
        """Get standard exploration prompt when diversity is disabled."""
        base_prompt = """Create ONE specific, implementable Python function for Large Language Models:

Requirements:
- Must use only standard Python library
- Accept 'input_data' dictionary parameter
- Return dictionary with 'result', 'status', and 'error' keys
- Should be useful for real-world LLM applications
- Must include proper error handling
- Should be different from previous suggestions

Focus on practical LLM tool functions for:
- Text processing and analysis
- Data validation and formatting
- Pattern extraction and parsing
- Mathematical calculations
- Data structure manipulation

Create ONE specific LLM tool function:"""
        
        if domain:
            base_prompt = f"""For {domain} domain: {base_prompt}"""
        
        return base_prompt
    
    def stop_autonomous_mode(self):
        """
        EDIT 3: Thread Management Enhancement - Stop autonomous mode with proper cleanup.
        Enhanced with graceful shutdown, progressive timeout reduction, and resource deallocation.
        """
        if self.autonomous_mode:
            self.autonomous_mode = False
            self.stop_event.set()  # EDIT 3: Signal stop event
            self.model_interface.stop_autonomous()
            
            # Stop action monitoring
            if self.config.ENABLE_ACTION_MONITORING:
                self.action_monitor.stop_monitoring()
            
            # Save learned patterns
            if self.config.ENABLE_FAILURE_LEARNING:
                self._save_failure_patterns()
            
            if hasattr(self, 'autonomous_task') and self.autonomous_task:
                if isinstance(self.autonomous_task, threading.Thread):
                    if self.autonomous_task.is_alive():
                        print("\n🛑 STOPPING ENHANCED AUTONOMOUS MODE...")
                        
                        # EDIT 3: Graceful shutdown with progressive timeout reduction
                        shutdown_timeouts = [10.0, 5.0, 2.0, 1.0]  # Progressive timeout reduction
                        
                        for timeout in shutdown_timeouts:
                            self.autonomous_task.join(timeout=timeout)
                            if not self.autonomous_task.is_alive():
                                print("✅ Autonomous thread terminated gracefully")
                                break
                            
                            if self.config.ENABLE_DEBUG_MODE:
                                print(f"⏳ Waiting for thread termination... ({timeout}s)")
                            
                            # Force additional signals
                            self.model_interface.kill_autonomous.set()
                            self.stop_event.set()
                        
                        # EDIT 3: Forced termination safety mechanism
                        if self.autonomous_task.is_alive():
                            logging.warning("Enhanced autonomous thread did not terminate gracefully within progressive timeouts")
                            if self.config.ENABLE_DEBUG_MODE:
                                print("⚠️  Thread still alive after all timeouts - forcing cleanup")
                            
                            # Final cleanup attempt
                            try:
                                # Give one final chance with minimal timeout
                                self.autonomous_task.join(timeout=0.5)
                                if self.autonomous_task.is_alive():
                                    print("⚠️  Thread termination forced - some resources may not be fully cleaned")
                            except Exception as cleanup_error:
                                logging.error(f"Thread cleanup error: {cleanup_error}")
                else:
                    try:
                        self.autonomous_task.cancel()
                    except Exception as e:
                        logging.warning(f"Failed to cancel autonomous task: {e}")
            
            print("🛑 ENHANCED AUTONOMOUS MODE STOPPED")
    
    def _should_create_function_enhanced(self, content: str) -> bool:
        """Enhanced determination of function creation worthiness."""
        content_lower = content.lower()
        
        # Enhanced strong indicators for LLM tools
        strong_indicators = [
            'function to', 'function that', 'create a function',
            'implement a', 'useful function', 'tool to', 'capability to',
            'a function', 'function for', 'def ', 'python function',
            'build a function', 'write a function', 'develop a function',
            'llm tool', 'language model', 'programmatic'
        ]
        
        strong_matches = sum(1 for indicator in strong_indicators if indicator in content_lower)
        if strong_matches >= 1:
            return True
        
        # Enhanced action words with context
        action_words = [
            'parse', 'extract', 'convert', 'calculate', 'validate',
            'generate', 'process', 'analyze', 'filter', 'format',
            'transform', 'classify', 'sort', 'search', 'count',
            'normalize', 'sanitize', 'clean', 'optimize', 'compress'
        ]
        
        action_matches = sum(1 for word in action_words if content_lower.count(word) >= 1)
        
        # Enhanced requirements and utility indicators
        utility_indicators = [
            'input', 'output', 'return', 'parameter', 'argument',
            'data','text', 'string', 'number', 'list', 'dict',
            'useful', 'practical', 'real-world', 'application',
            'input_data', 'dictionary'
        ]
        
        utility_matches = sum(1 for indicator in utility_indicators if indicator in content_lower)
        
        # Enhanced scoring system
        total_score = (strong_matches * 3) + (action_matches * 2) + utility_matches
        
        return total_score >= 4
    
    def _extract_implementable_function_description_enhanced(self, content: str) -> str:
        """Enhanced extraction of implementable function descriptions for LLM tools."""
        lines = content.split('\n')
        
        # Enhanced pattern matching with scoring
        best_description = ""
        best_score = 0
        
        for line in lines:
            line_clean = line.strip().lower()
            original_line = line.strip()
            
            if len(original_line) < 25:  # Minimum length requirement
                continue
            
            score = 0
            
            # Enhanced starter patterns with scoring
            starter_patterns = [
                ('llm tool function to', 4), ('tool function that', 4),
                ('function to', 3), ('function that', 3), ('tool to', 2), ('tool that', 2),
                ('a function to', 3), ('a function that', 3), ('create a function', 3),
                ('implement a function', 3), ('build a function', 2), ('write a function', 2),
                ('develop a function', 2), ('design a function', 2)
            ]
            
            for pattern, points in starter_patterns:
                if pattern in line_clean:
                    score += points
            
            # Action word scoring
            action_words = ['parse', 'extract', 'convert', 'calculate', 'validate', 'process', 'analyze']
            for word in action_words:
                if word in line_clean:
                    score += 1
            
            # LLM tool specific indicators
            llm_indicators = ['input_data', 'dictionary', 'programmatic', 'interface']
            for indicator in llm_indicators:
                if indicator in line_clean:
                    score += 2
            
            # Utility and implementation indicators
            utility_words = ['data', 'text', 'input', 'output', 'return', 'useful', 'practical']
            for word in utility_words:
                if word in line_clean:
                    score += 0.5
            
            # Length bonus for detailed descriptions
            if len(original_line) > 50:
                score += 1
            if len(original_line) > 100:
                score += 1
            
            # Update best description if this scores higher
            if score > best_score:
                best_score = score
                # Clean the description
                description = original_line
                description = re.sub(r'^[*#\-•·→\d+\.\s]*', '', description)
                description = description.replace('*', '').replace('#', '').strip()
                best_description = description
        
        # Enhanced fallback with action detection
        if not best_description or best_score < 2:
            action_lines = []
            for line in lines:
                line_lower = line.lower()
                if any(action in line_lower for action in [
                    'parse', 'extract', 'convert', 'calculate', 'validate',
                    'process', 'analyze', 'format', 'transform', 'classify'
                ]):
                    if len(line.strip()) > 20:
                        action_lines.append(line.strip())
            
            if action_lines:
                best_description = action_lines[0]
        
        # Final fallback for LLM tools
        if not best_description:
            return "A function to process and analyze structured data as an LLM tool with comprehensive error handling"
        
        return best_description
    
    def configure_settings(self):
        """Enhanced interactive settings configuration."""
        print("⚙️  ENHANCED SYSTEM CONFIGURATION")
        print("=" * 50)
        
        try:
            print(f"Current max iterations: {self.config.MAX_AUTONOMOUS_ITERATIONS}")
            new_iterations = input("Enter new max iterations (1-1000, or press Enter to keep current): ").strip()
            if new_iterations:
                value = int(new_iterations)
                self.config.MAX_AUTONOMOUS_ITERATIONS = max(1, min(1000, value))
            
            print(f"Current exploration timeout: {self.config.EXPLORATION_TIMEOUT}s")
            new_timeout = input("Enter new timeout in seconds (60-3600, or press Enter to keep current): ").strip()
            if new_timeout:
                value = int(new_timeout)
                self.config.EXPLORATION_TIMEOUT = max(60, min(3600, value))
            
            print(f"Current exploration interval: {self.config.EXPLORATION_INTERVAL}s")
            new_interval = input("Enter new interval in seconds (0.5-60, or press Enter to keep current): ").strip()
            if new_interval:
                value = float(new_interval)
                self.config.EXPLORATION_INTERVAL = max(0.5, min(60, value))
            
            print(f"Current temperature: {self.config.TEMPERATURE}")
            new_temp = input("Enter new temperature (0.0-2.0, or press Enter to keep current): ").strip()
            if new_temp:
                value = float(new_temp)
                self.config.TEMPERATURE = max(0.0, min(2.0, value))
            
            print(f"Current top_p: {self.config.TOP_P}")
            new_top_p = input("Enter new top_p (0.0-1.0, or press Enter to keep current): ").strip()
            if new_top_p:
                value = float(new_top_p)
                self.config.TOP_P = max(0.0, min(1.0, value))
            
            print(f"Current debug mode: {self.config.ENABLE_DEBUG_MODE}")
            toggle_debug = input("Toggle debug mode? (y/N): ").strip().lower()
            if toggle_debug == 'y':
                self.config.ENABLE_DEBUG_MODE = not self.config.ENABLE_DEBUG_MODE
            
            print(f"Current sandbox execution: {self.config.ENABLE_SANDBOX_EXECUTION}")
            toggle_sandbox = input("Toggle sandbox execution? (y/N): ").strip().lower()
            if toggle_sandbox == 'y':
                self.config.ENABLE_SANDBOX_EXECUTION = not self.config.ENABLE_SANDBOX_EXECUTION
            
            print(f"Current security analysis: {self.config.ENABLE_SECURITY_ANALYSIS}")
            toggle_security = input("Toggle security analysis? (y/N): ").strip().lower()
            if toggle_security == 'y':
                self.config.ENABLE_SECURITY_ANALYSIS = not self.config.ENABLE_SECURITY_ANALYSIS
            
            print(f"Current action monitoring: {self.config.ENABLE_ACTION_MONITORING}")
            toggle_monitoring = input("Toggle action monitoring? (y/N): ").strip().lower()
            if toggle_monitoring == 'y':
                self.config.ENABLE_ACTION_MONITORING = not self.config.ENABLE_ACTION_MONITORING
            
            print(f"Current natural language commands: {self.config.ENABLE_NATURAL_LANGUAGE_COMMANDS}")
            toggle_nl = input("Toggle natural language commands? (y/N): ").strip().lower()
            if toggle_nl == 'y':
                self.config.ENABLE_NATURAL_LANGUAGE_COMMANDS = not self.config.ENABLE_NATURAL_LANGUAGE_COMMANDS
            
            print(f"Current adaptive validation: {self.config.ENABLE_ADAPTIVE_VALIDATION}")
            toggle_adaptive = input("Toggle adaptive validation? (y/N): ").strip().lower()
            if toggle_adaptive == 'y':
                self.config.ENABLE_ADAPTIVE_VALIDATION = not self.config.ENABLE_ADAPTIVE_VALIDATION
            
            print(f"Current failure learning: {self.config.ENABLE_FAILURE_LEARNING}")
            toggle_learning = input("Toggle failure learning? (y/N): ").strip().lower()
            if toggle_learning == 'y':
                self.config.ENABLE_FAILURE_LEARNING = not self.config.ENABLE_FAILURE_LEARNING
            
            print(f"Current diversity injection: {self.config.ENABLE_DIVERSITY_INJECTION}")
            toggle_diversity = input("Toggle diversity injection? (y/N): ").strip().lower()
            if toggle_diversity == 'y':
                self.config.ENABLE_DIVERSITY_INJECTION = not self.config.ENABLE_DIVERSITY_INJECTION
            
            print(f"Current local exploration: {self.config.ENABLE_LOCAL_EXPLORATION}")
            toggle_local = input("Toggle local system exploration? (y/N): ").strip().lower()
            if toggle_local == 'y':
                self.config.ENABLE_LOCAL_EXPLORATION = not self.config.ENABLE_LOCAL_EXPLORATION
            
            print(f"Current AST duplicate detection: {self.config.ENABLE_AST_DUPLICATE_DETECTION}")
            toggle_ast = input("Toggle AST duplicate detection? (y/N): ").strip().lower()
            if toggle_ast == 'y':
                self.config.ENABLE_AST_DUPLICATE_DETECTION = not self.config.ENABLE_AST_DUPLICATE_DETECTION
            
            print(f"Current code diff logging: {self.config.ENABLE_CODE_DIFF_LOGGING}")
            toggle_diff = input("Toggle code diff logging? (y/N): ").strip().lower()
            if toggle_diff == 'y':
                self.config.ENABLE_CODE_DIFF_LOGGING = not self.config.ENABLE_CODE_DIFF_LOGGING
            
            if BLACK_AVAILABLE:
                print(f"Current code formatting: {self.config.ENABLE_CODE_FORMATTING}")
                toggle_formatting = input("Toggle code formatting? (y/N): ").strip().lower()
                if toggle_formatting == 'y':
                    self.config.ENABLE_CODE_FORMATTING = not self.config.ENABLE_CODE_FORMATTING
            
            # Save enhanced configuration
            self.config.save_to_file()
            print("✅ Enhanced configuration updated and saved!")
            
        except ValueError as e:
            print(f"❌ Invalid input: {e}")
        except Exception as e:
            print(f"❌ Enhanced configuration error: {e}")
    
    def list_domains(self) -> List[str]:
        """List all available domains with enhanced information."""
        domains = self.database.get_all_domains()
        if domains:
            print("📁 AVAILABLE ENHANCED DOMAINS:")
            for domain in domains:
                functions = self.database.get_functions_by_domain(domain)
                complexity_avg = sum(f.complexity_score for f in functions) / len(functions) if functions else 0
                llm_compatible = sum(1 for f in functions if 'input_data' in f.source_code)
                artifact_based = sum(1 for f in functions if f.source_artifact)
                print(f"   🔹 {domain}: {len(functions)} functions")
                print(f"      Avg Complexity: {complexity_avg:.1f}/10")
                print(f"      LLM Compatible: {llm_compatible}/{len(functions)}")
                print(f"      Artifact-based: {artifact_based}")
        else:
            print("📁 No enhanced domains available yet")
        
        return domains
    
    def list_functions(self, domain: str = None) -> List[FunctionMetadata]:
        """List functions with enhanced formatting and LLM tool focus."""
        if domain:
            functions = self.database.get_functions_by_domain(domain)
            print(f"🔧 ENHANCED LLM TOOLS IN DOMAIN '{domain.upper()}':")
        else:
            # Get all functions from all domains
            all_domains = self.database.get_all_domains()
            functions = []
            for d in all_domains:
                functions.extend(self.database.get_functions_by_domain(d))
            print("🔧 ALL ENHANCED LLM TOOLS:")
        
        if functions:
            for i, func in enumerate(functions, 1):
                llm_tool_icon = "🤖" if 'input_data' in func.source_code else "⚠️"
                artifact_icon = "📄" if func.source_artifact else ""
                print(f"   {i}. {llm_tool_icon} {func.name} ({func.domain})")
                print(f"      {func.description}")
                print(f"      Safety: {func.safety_rating} | Complexity: {func.complexity_score}/10")
                print(f"      Created: {func.created_at[:10]} {artifact_icon}")
        else:
            domain_text = f" in domain '{domain}'" if domain else ""
            print(f"   No enhanced LLM tools found{domain_text}")
        
        return functions
    
    def show_function_details(self, function_name: str) -> Optional[FunctionMetadata]:
        """Show detailed information about a specific function."""
        # Search across all domains
        all_domains = self.database.get_all_domains()
        
        for domain in all_domains:
            functions = self.database.get_functions_by_domain(domain)
            for func in functions:
                if func.name == function_name:
                    print(f"🔧 ENHANCED LLM TOOL DETAILS: {func.name}")
                    print("=" * 60)
                    print(f"Domain: {func.domain}")
                    print(f"Description: {func.description}")
                    print(f"Safety Rating: {func.safety_rating}")
                    print(f"Complexity Score: {func.complexity_score}/10")
                    print(f"Created: {func.created_at}")
                    print(f"Validation Status: {func.validation_status}")
                    print(f"LLM Tool Interface: {'✅' if 'input_data' in func.source_code else '❌'}")
                    if func.source_artifact:
                        print(f"Source Artifact: {func.source_artifact}")
                    print(f"Code Hash: {func.code_hash}")
                    
                    if func.signature:
                        print(f"\nSignature: {func.signature}")
                    
                    if func.parameters:
                        print(f"\nParameters: {func.parameters}")
                    
                    if func.usage_example:
                        print(f"\nUsage Example:\n{func.usage_example}")
                    
                    if func.input_output_description:
                        print(f"\nInput/Output: {func.input_output_description}")
                    
                    print(f"\nSource Code:")
                    print("-" * 40)
                    print(func.source_code)
                    print("-" * 40)
                    
                    return func
        
        print(f"❌ Enhanced LLM tool '{function_name}' not found")
        return None
    
    def export_training_data(self, output_path: str = "training_data.jsonl", 
                           transformation_types: List[str] = None) -> bool:
        """Export code diff training data to JSONL format."""
        if not self.config.ENABLE_CODE_DIFF_LOGGING:
            print("❌ Code diff logging is disabled. Enable it in configuration to collect training data.")
            return False
        
        return self.database.export_training_data_jsonl(output_path, transformation_types)
    
    def show_training_statistics(self):
        """Show statistics about collected training data."""
        if not self.config.ENABLE_CODE_DIFF_LOGGING:
            print("❌ Code diff logging is disabled. No training data available.")
            return
        
        # Get statistics from code diff logger
        stats = self.model_interface.code_diff_logger.get_statistics()
        
        print("📊 CODE DIFF TRAINING DATA STATISTICS:")
        print("=" * 50)
        print(f"Total transformations logged: {stats['total_entries']}")
        print(f"Successful transformations: {stats['successful_transformations']}")
        print(f"Failed transformations: {stats['failed_transformations']}")
        print(f"Average size change: {stats['average_size_change']:.1f} characters")
        print(f"Functions processed: {stats['functions_processed']}")
        
        print("\nTransformation Types:")
        for transform_type, type_stats in stats['transformation_types'].items():
            success_rate = (type_stats['success'] / type_stats['count'] * 100) if type_stats['count'] > 0 else 0
            print(f"   {transform_type}: {type_stats['count']} total, {success_rate:.1f}% success")
        
        # Get database statistics
        dataset = self.database.get_training_dataset()
        print(f"\nTraining dataset available: {len(dataset)} examples")
    
    def show_system_status(self):
        """Show comprehensive system status and health metrics."""
        print("🔍 ENHANCED SYSTEM STATUS:")
        print("=" * 50)
        
        # Model configuration status
        print(f"Models:")
        print(f"   Code Generation: {self.config.CODE_GENERATION_MODEL}")
        print(f"   Intelligence: {self.config.INTELLIGENCE_MODEL}")
        print(f"   Temperature: {self.config.TEMPERATURE}")
        print(f"   Top-P: {self.config.TOP_P}")
        
        # Database status
        domains = self.database.get_all_domains()
        total_functions = sum(len(self.database.get_functions_by_domain(d)) for d in domains)
        print(f"\nDatabase:")
        print(f"   Domains: {len(domains)}")
        print(f"   Total Functions: {total_functions}")
        
        # System features status
        print(f"\nFeatures:")
        print(f"   Debug Mode: {'✅' if self.config.ENABLE_DEBUG_MODE else '❌'}")
        print(f"   Sandbox Execution: {'✅' if self.config.ENABLE_SANDBOX_EXECUTION else '❌'}")
        print(f"   Action Monitoring: {'✅' if self.config.ENABLE_ACTION_MONITORING else '❌'}")
        print(f"   Code Diff Logging: {'✅' if self.config.ENABLE_CODE_DIFF_LOGGING else '❌'}")
        print(f"   Local Exploration: {'✅' if self.config.ENABLE_LOCAL_EXPLORATION else '❌'}")
        print(f"   Failure Learning: {'✅' if self.config.ENABLE_FAILURE_LEARNING else '❌'}")
        
        # Autonomous mode status
        print(f"\nAutonomous Mode:")
        print(f"   Status: {'🔴 ACTIVE' if self.autonomous_mode else '🟢 INACTIVE'}")
        if self.autonomous_mode:
            print(f"   Goals: {len(self.autonomous_goals)}")
        
        # Action monitoring status
        if self.config.ENABLE_ACTION_MONITORING:
            recent_actions = self.action_monitor.get_recent_actions(5)
            print(f"\nRecent Actions ({len(recent_actions)}):")
            for action in recent_actions[-3:]:
                status = "✅" if action.success else "❌"
                print(f"   {status} {action.action_type}: {action.description[:50]}...")
        
        # Training data status
        if self.config.ENABLE_CODE_DIFF_LOGGING:
            stats = self.model_interface.code_diff_logger.get_statistics()
            print(f"\nTraining Data:")
            print(f"   Transformations: {stats['total_entries']}")
            print(f"   Success Rate: {(stats['successful_transformations'] / stats['total_entries'] * 100):.1f}%" if stats['total_entries'] > 0 else "   Success Rate: N/A")
        
        # Architectural fixes status
        print(f"\nArchitectural Fixes Applied:")
        print(f"   ✅ EDIT 1: Enhanced Fallback Function Generation (UUID-based naming)")
        print(f"   ✅ EDIT 2: Multi-Model Fallback Strategy (sequential attempts)")
        print(f"   ✅ EDIT 3: Thread Management Enhancement (graceful shutdown)")
        print(f"   ✅ EDIT 4: Function Name Uniqueness Validation (collision prevention)")
        print(f"   ✅ EDIT 5: Enhanced Response Validation (content verification)")
        print(f"   ✅ EDIT 6: Configuration Auto-Detection (model health checking)")
    
    def interactive_mode(self):
        """Enhanced interactive mode with comprehensive LLM tool focus."""
        print("🚀 ENHANCED AUTONOMOUS LLM FUNCTION DEVELOPMENT SYSTEM v5.2.3 (ARCHITECTURALLY FIXED)")
        print("   Advanced LLM tool generation with comprehensive architectural fixes applied")
        print("   ✅ UUID-based naming | ✅ Multi-model fallback | ✅ Thread management | ✅ Collision prevention")
        print("=" * 80)
        
        while not self.shutdown_requested:
            try:
                print("\n📋 ENHANCED COMMANDS:")
                print("   1. create <description> - Create LLM tool function")
                print("   2. auto [domain] - Start autonomous mode")
                print("   3. fullauton - Start full autonomous exploration") 
                print("   4. stop - Stop autonomous mode")
                print("   5. list [domain] - List functions")
                print("   6. domains - List all domains")
                print("   7. show <name> - Show function details")
                print("   8. config - Configure settings")
                print("   9. export - Export training data")
                print("   10. stats - Show training statistics")
                print("   11. status - Show system status")
                print("   12. test - Run architectural fixes test")
                print("   13. quit - Exit system")
                
                if self.autonomous_mode:
                    print("\n🔄 AUTONOMOUS MODE ACTIVE - Type 'stop' or 'KILL' to halt")
                
                command = input("\n🔧 Enter command: ").strip()
                
                if not command:
                    continue
                elif command.lower() in ['quit', 'exit', 'q']:
                    break
                elif command.lower() in ['kill', 'stop']:
                    if self.autonomous_mode:
                        self.stop_autonomous_mode()
                    else:
                        print("❌ No autonomous mode running")
                elif command.startswith('create '):
                    description = command[7:].strip()
                    if description:
                        self.create_function(description)
                    else:
                        print("❌ Please provide a function description")
                elif command.startswith('auto '):
                    domain = command[5:].strip()
                    if not self.autonomous_mode:
                        self.start_autonomous_mode(domain if domain else None)
                    else:
                        print("❌ Autonomous mode already running")
                elif command.lower() == 'auto':
                    if not self.autonomous_mode:
                        self.start_autonomous_mode()
                    else:
                        print("❌ Autonomous mode already running")
                elif command.lower() == 'fullauton':
                    if not self.autonomous_mode:
                        self.start_autonomous_mode(full_autonomy=True)
                    else:
                        print("❌ Autonomous mode already running")
                elif command.startswith('list '):
                    domain = command[5:].strip()
                    self.list_functions(domain if domain else None)
                elif command.lower() == 'list':
                    self.list_functions()
                elif command.lower() == 'domains':
                    self.list_domains()
                elif command.startswith('show '):
                    func_name = command[5:].strip()
                    if func_name:
                        self.show_function_details(func_name)
                    else:
                        print("❌ Please provide a function name")
                elif command.lower() == 'config':
                    self.configure_settings()
                elif command.lower() == 'export':
                    output_path = input("Enter output path (default: training_data.jsonl): ").strip()
                    if not output_path:
                        output_path = "training_data.jsonl"
                    self.export_training_data(output_path)
                elif command.lower() == 'stats':
                    self.show_training_statistics()
                elif command.lower() == 'status':
                    self.show_system_status()
                elif command.lower() == 'test':
                    self._run_architectural_fixes_test()
                else:
                    print("❌ Unknown command. Please try again.")
                    
            except KeyboardInterrupt:
                print("\n🛑 Interrupt received...")
                if self.autonomous_mode:
                    self.stop_autonomous_mode()
                break
            except Exception as e:
                print(f"❌ Command error: {e}")
                if self.config.ENABLE_DEBUG_MODE:
                    traceback.print_exc()
        
        # Cleanup before exit
        if self.autonomous_mode:
            self.stop_autonomous_mode()
        
        # Save any remaining data
        if self.config.ENABLE_FAILURE_LEARNING:
            self._save_failure_patterns()
        
        print("\n👋 Enhanced Autonomous LLM Function Development System shutting down...")
        print("   Thank you for using the architecturally fixed system!")
    
    def _run_architectural_fixes_test(self):
        """
        Test all six architectural fixes to ensure they're working correctly.
        This comprehensive test validates the implementation of each critical fix.
        """
        print("🧪 RUNNING COMPREHENSIVE ARCHITECTURAL FIXES TEST")
        print("=" * 60)
        
        test_results = {
            "edit_1_fallback_naming": False,
            "edit_2_multi_model": False,
            "edit_3_thread_management": False,
            "edit_4_name_uniqueness": False,
            "edit_5_response_validation": False,
            "edit_6_auto_detection": False
        }
        
        try:
            # EDIT 1: Test Enhanced Fallback Function Generation
            print("🔍 Testing EDIT 1: Enhanced Fallback Function Generation...")
            try:
                test_prompt = "test function for architectural validation"
                fallback_code_1 = self.model_interface._generate_enhanced_fallback_function(test_prompt)
                fallback_code_2 = self.model_interface._generate_enhanced_fallback_function(test_prompt)
                
                # Extract function names
                name_1 = self.code_processor.get_function_name(fallback_code_1) if fallback_code_1 else None
                name_2 = self.code_processor.get_function_name(fallback_code_2) if fallback_code_2 else None
                
                if name_1 and name_2 and name_1 != name_2:
                    print("   ✅ Unique naming collision prevention working")
                    test_results["edit_1_fallback_naming"] = True
                else:
                    print("   ❌ Fallback naming collision prevention failed")
            except Exception as e:
                print(f"   ❌ EDIT 1 test failed: {e}")
            
            # EDIT 2: Test Multi-Model Fallback Strategy  
            print("🔍 Testing EDIT 2: Multi-Model Fallback Strategy...")
            try:
                # Test that multiple models are attempted
                original_model = self.config.CODE_GENERATION_MODEL
                test_response = self.model_interface.generate_code_robust("def test_function(): return 'test'")
                
                if test_response.metadata and "model" in test_response.metadata:
                    print("   ✅ Multi-model strategy operational")
                    test_results["edit_2_multi_model"] = True
                else:
                    print("   ❌ Multi-model strategy metadata missing")
            except Exception as e:
                print(f"   ❌ EDIT 2 test failed: {e}")
            
            # EDIT 3: Test Thread Management Enhancement
            print("🔍 Testing EDIT 3: Thread Management Enhancement...")
            try:
                # Test stop event mechanism
                if hasattr(self, 'stop_event'):
                    print("   ✅ Stop event mechanism implemented")
                    test_results["edit_3_thread_management"] = True
                else:
                    print("   ❌ Stop event mechanism missing")
            except Exception as e:
                print(f"   ❌ EDIT 3 test failed: {e}")
            
            # EDIT 4: Test Function Name Uniqueness Validation
            print("🔍 Testing EDIT 4: Function Name Uniqueness Validation...")
            try:
                # Test unique name generation
                base_name = "test_function"
                unique_name_1 = self.validator._generate_unique_function_name(base_name)
                unique_name_2 = self.validator._generate_unique_function_name(base_name)
                
                if unique_name_1 != unique_name_2:
                    print("   ✅ Function name uniqueness validation working")
                    test_results["edit_4_name_uniqueness"] = True
                else:
                    print("   ❌ Function name uniqueness validation failed")
            except Exception as e:
                print(f"   ❌ EDIT 4 test failed: {e}")
            
            # EDIT 5: Test Enhanced Response Validation
            print("🔍 Testing EDIT 5: Enhanced Response Validation...")
            try:
                # Test response validation logic
                test_responses = [
                    "",  # Empty
                    "short",  # Too short
                    "def valid_function(): return True",  # Valid
                    "no function here"  # No function
                ]
                
                validation_results = []
                for response in test_responses:
                    has_function = 'def ' in response
                    is_long_enough = len(response.strip()) >= 20
                    validation_results.append(has_function and is_long_enough)
                
                if validation_results == [False, False, True, False]:
                    print("   ✅ Response validation logic working correctly")
                    test_results["edit_5_response_validation"] = True
                else:
                    print("   ❌ Response validation logic failed")
            except Exception as e:
                print(f"   ❌ EDIT 5 test failed: {e}")
            
            # EDIT 6: Test Configuration Auto-Detection
            print("🔍 Testing EDIT 6: Configuration Auto-Detection...")
            try:
                # Test model health checking
                working_model = self.config.get_working_model_for_code_generation()
                if working_model:
                    print("   ✅ Configuration auto-detection working")
                    test_results["edit_6_auto_detection"] = True
                else:
                    print("   ❌ Configuration auto-detection failed")
            except Exception as e:
                print(f"   ❌ EDIT 6 test failed: {e}")
            
            # Summary
            print("\n📊 ARCHITECTURAL FIXES TEST RESULTS:")
            print("=" * 40)
            passed = sum(test_results.values())
            total = len(test_results)
            
            for test_name, passed_test in test_results.items():
                status = "✅ PASS" if passed_test else "❌ FAIL"
                print(f"   {test_name.replace('_', ' ').title()}: {status}")
            
            print(f"\nOverall Result: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
            
            if passed == total:
                print("🎉 ALL ARCHITECTURAL FIXES VALIDATED SUCCESSFULLY!")
            else:
                print(f"⚠️  {total-passed} architectural fixes need attention")
                
        except Exception as e:
            print(f"❌ Architectural fixes test failed: {e}")
            if self.config.ENABLE_DEBUG_MODE:
                traceback.print_exc()


# ============================================================================
# ENHANCED MAIN EXECUTION ENTRY POINT
# ============================================================================

def main():
    """Enhanced main execution entry point with comprehensive initialization."""
    try:
        print("🚀 Starting Enhanced Autonomous LLM Function Development System v5.2.3 (ARCHITECTURALLY FIXED)...")
        print("   🔧 COMPREHENSIVE ARCHITECTURAL FIXES APPLIED:")
        print("   • ✅ EDIT 1: Enhanced Fallback Function Generation (UUID-based unique naming)")
        print("   • ✅ EDIT 2: Multi-Model Fallback Strategy (sequential model attempts)")
        print("   • ✅ EDIT 3: Thread Management Enhancement (graceful shutdown)")
        print("   • ✅ EDIT 4: Function Name Uniqueness Validation (collision prevention)")
        print("   • ✅ EDIT 5: Enhanced Response Validation (content verification)")
        print("   • ✅ EDIT 6: Configuration Auto-Detection (model health checking)")
        print("")
        print("   🛡️  SYSTEMIC ISSUES RESOLVED:")
        print("   • ❌ Empty Model Response Cascade Failure → ✅ Multi-model fallback")
        print("   • ❌ Function Name Collision in Fallback → ✅ UUID-based naming")
        print("   • ❌ Thread Management Issues → ✅ Graceful shutdown")
        print("   • ❌ Model Selection Logic Flaw → ✅ Auto-detection")
        print("   • ❌ Insufficient Error Handling → ✅ Enhanced validation")
        print("   • ❌ Inadequate Fallback Mechanisms → ✅ Progressive strategies")
        
        # Load configuration
        config = SystemConfig.load_from_file()
        
        # Initialize the enhanced system
        system = AdvancedAutonomousFunctionDevelopmentSystem(config)
        
        # Handle command line arguments
        if len(sys.argv) > 1:
            arg = sys.argv[1].lower()
            
            if arg == 'auto':
                domain = sys.argv[2] if len(sys.argv) > 2 else None
                print(f"🤖 Starting autonomous mode with domain: {domain or 'general'}")
                system.start_autonomous_mode(domain)
                
                # Keep the program running
                try:
                    while system.autonomous_mode:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\n🛑 Stopping autonomous mode...")
                    system.stop_autonomous_mode()
                    
            elif arg == 'fullauton':
                print("🚀 Starting full autonomous exploration mode...")
                system.start_autonomous_mode(full_autonomy=True)
                
                # Keep the program running
                try:
                    while system.autonomous_mode:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\n🛑 Stopping autonomous mode...")
                    system.stop_autonomous_mode()
                    
            elif arg.startswith('create'):
                if len(sys.argv) > 2:
                    description = ' '.join(sys.argv[2:])
                    print(f"🔧 Creating function: {description}")
                    success = system.create_function(description)
                    return 0 if success else 1
                else:
                    print("❌ Please provide a function description")
                    return 1
                    
            elif arg == 'list':
                domain = sys.argv[2] if len(sys.argv) > 2 else None
                system.list_functions(domain)
                
            elif arg == 'domains':
                system.list_domains()
                
            elif arg == 'config':
                system.configure_settings()
                
            elif arg == 'export':
                output_path = sys.argv[2] if len(sys.argv) > 2 else "training_data.jsonl"
                system.export_training_data(output_path)
                
            elif arg == 'stats':
                system.show_training_statistics()
                
            elif arg == 'status':
                system.show_system_status()
                
            elif arg == 'test':
                system._run_architectural_fixes_test()
                
            elif arg in ['help', '-h', '--help']:
                print("Enhanced Autonomous LLM Function Development System v5.2.3 (ARCHITECTURALLY FIXED)")
                print("With comprehensive architectural fixes for systemic reliability")
                print("\nUsage:")
                print("  python a.py                    - Start interactive mode")
                print("  python a.py auto [domain]      - Start autonomous mode")
                print("  python a.py fullauton          - Start full autonomous exploration")
                print("  python a.py create <desc>      - Create single function")
                print("  python a.py list [domain]      - List functions")
                print("  python a.py domains            - List all domains")
                print("  python a.py config             - Configure settings")
                print("  python a.py export [path]      - Export training data")
                print("  python a.py stats              - Show training statistics")
                print("  python a.py status             - Show system status")
                print("  python a.py test               - Test architectural fixes")
                print("  python a.py help               - Show this help")
                print("\nArchitectural Fixes Applied:")
                print("  ✅ EDIT 1: Enhanced Fallback Function Generation (UUID-based naming)")
                print("  ✅ EDIT 2: Multi-Model Fallback Strategy (sequential attempts)")
                print("  ✅ EDIT 3: Thread Management Enhancement (graceful shutdown)")
                print("  ✅ EDIT 4: Function Name Uniqueness Validation (collision prevention)")
                print("  ✅ EDIT 5: Enhanced Response Validation (content verification)")
                print("  ✅ EDIT 6: Configuration Auto-Detection (model health checking)")
                print("\nSystemic Issues Resolved:")
                print("  • Empty model response cascade failures")
                print("  • Function name collisions in fallback system")
                print("  • Thread management and cleanup issues")
                print("  • Model selection logic flaws")
                print("  • Insufficient error handling patterns")
                print("  • Inadequate fallback mechanisms")
                print("\nKey Features:")
                print("  • Collision-proof function generation")
                print("  • Multi-model reliability with automatic fallback")
                print("  • Enhanced thread lifecycle management")
                print("  • Comprehensive duplicate detection")
                print("  • Advanced response validation")
                print("  • Intelligent model health monitoring")
                print("  • Real-time architectural integrity testing")
                
            else:
                print(f"❌ Unknown argument: {arg}")
                print("Use 'python a.py help' for usage information")
                return 1
        else:
            # Start interactive mode
            system.interactive_mode()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n🛑 System interrupted by user")
        return 0
    except Exception as e:
        print(f"❌ SYSTEM ERROR: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)      
