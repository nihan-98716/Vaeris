import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Resolve log file path
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "vaeris.log"

class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs log messages in a structured JSON format.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        
        # Standard Python logging puts extra keys directly on the record
        standard_attrs = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'message', 'msg', 'name', 'pathname', 'process', 'processName',
            'relativeCreated', 'stack_info', 'thread', 'threadName'
        }
        
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                log_data[key] = value

        return json.dumps(log_data)

class ConsoleFormatter(logging.Formatter):
    """
    Friendly, highly readable formatter for local development console output.
    """
    # ANSI escape codes for colors
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[41m', # Red background
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '')
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        level_str = f"{color}[{record.levelname}]{self.RESET}"
        module_str = f"[{record.module}]"
        
        msg = record.getMessage()
        
        # Format extra properties as key-value pairs
        extra_parts = []
        standard_attrs = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'message', 'msg', 'name', 'pathname', 'process', 'processName',
            'relativeCreated', 'stack_info', 'thread', 'threadName'
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                extra_parts.append(f"{key}={value}")
                
        extra_str = f" | {' '.join(extra_parts)}" if extra_parts else ""
        
        return f"{timestamp} {level_str:<18} {module_str:<15} {msg}{extra_str}"

def setup_logger(name: str = "vaeris") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if setup is called multiple times
    if logger.handlers:
        return logger

    # Console handler (standard output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(console_handler)

    # File handler (JSON format for structured logs)
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create file handler for logger: {e}", file=sys.stderr)

    return logger

# Singleton logger instance
logger = setup_logger()
