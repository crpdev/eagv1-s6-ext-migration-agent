import logging
import logging.handlers
import os
import sys
import json
from datetime import datetime
from typing import Optional, Dict, Any

def setup_logging(log_file_path=None, log_level=logging.INFO):
    """
    Set up logging configuration with both console and file handlers.
    
    Args:
        log_file_path (str): Path to the log file. If None, uses default path.
        log_level (int): Logging level to use. Defaults to INFO.
    """
    try:
        # Create logs directory if it doesn't exist
        if log_file_path is None:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            log_file_path = os.path.join(log_dir, f'app_{datetime.now().strftime("%Y%m%d")}.log')
        
        # Create formatters
        formatter = SafeFormatter(
            '%(asctime)s | %(levelname)s | %(thread_process)s%(function_info)s | %(message)s%(extra_data)s'
        )
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Remove existing handlers to prevent duplicate logging
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)
        
        # File Handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)
        
        # Log startup message
        root_logger.info(f"Logging initialized. Log file: {log_file_path}")
        
    except Exception as e:
        # Ensure basic logging is available even if setup fails
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        logging.error(f"Failed to setup logging: {str(e)}")
        raise

class SafeFormatter(logging.Formatter):
    def format(self, record):
        # Ensure extra_data exists and is properly formatted
        if not hasattr(record, 'extra_data'):
            record.extra_data = ''
        elif record.extra_data:
            # If extra_data is not empty, add a separator
            record.extra_data = f" | {record.extra_data}"
        
        # Add thread name and process ID
        thread_info = f"[Thread: {record.threadName}]" if hasattr(record, 'threadName') else ''
        process_info = f"[PID: {record.process}]" if hasattr(record, 'process') else ''
        
        # Add function name if available
        func_info = f"[{record.funcName}]" if hasattr(record, 'funcName') else ''
        
        # Add these to record
        record.thread_process = f"{thread_info}{process_info}"
        record.function_info = func_info
        
        try:
            return super().format(record)
        except ValueError as e:
            # If formatting fails, return a simplified format
            return f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {record.levelname} | {record.message}"
        
    def formatException(self, ei):
        """Enhanced exception formatting."""
        result = super().formatException(ei)
        return f"\nException Details:\n{result}"

class ExtraDataAdapter(logging.LoggerAdapter):
    """Enhanced adapter to add extra data to log records in a structured way."""
    
    def format_extra_data(self, data: Any) -> str:
        """Format extra data in a consistent way."""
        if isinstance(data, dict):
            # Convert dict to a formatted string
            try:
                return json.dumps(data, indent=None, sort_keys=True)
            except Exception:
                return str(data)
        return str(data)
    
    def process(self, msg, kwargs):
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        if 'extra_data' not in kwargs['extra']:
            kwargs['extra']['extra_data'] = ''
            
        # Handle extra data
        extra_data = kwargs.get('extra_data', kwargs['extra'].get('extra_data', ''))
        if extra_data:
            formatted_data = self.format_extra_data(extra_data)
            kwargs['extra']['extra_data'] = f" | {formatted_data}"
            
        # Add call stack depth for debugging if needed
        if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
            import inspect
            stack_depth = len(inspect.stack())
            kwargs['extra']['extra_data'] += f" | Stack depth: {stack_depth}"
            
        return msg, kwargs

def get_logger(name: str) -> ExtraDataAdapter:
    """Get a logger instance with the ExtraDataAdapter.
    
    Args:
        name: Logger name, typically __name__ of the module
        
    Returns:
        Configured logger instance with ExtraDataAdapter
    """
    logger = logging.getLogger(name)
    return ExtraDataAdapter(logger, {})

# Performance logging decorator
def log_performance(logger):
    """Decorator to log function performance."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                logger.debug(f"Function {func.__name__} completed",
                           extra={"duration_seconds": duration})
                return result
            except Exception as e:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                logger.error(f"Function {func.__name__} failed after {duration:.2f}s: {str(e)}",
                           exc_info=True)
                raise
        return wrapper
    return decorator