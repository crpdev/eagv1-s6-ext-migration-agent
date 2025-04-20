import logging
import logging.handlers
import os
import sys
import json
from datetime import datetime
from typing import Optional, Dict, Any

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """Set up logging configuration."""
    # Clean up the log level string and handle comments
    log_level = log_level.split('#')[0].strip().upper()
    
    # Create logs directory if it doesn't exist
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
    
    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    class SafeFormatter(logging.Formatter):
        def format(self, record):
            if not hasattr(record, 'extra_data'):
                record.extra_data = ''
            
            # Add thread name and process ID
            thread_info = f"[Thread: {record.threadName}]" if hasattr(record, 'threadName') else ''
            process_info = f"[PID: {record.process}]" if hasattr(record, 'process') else ''
            
            # Add function name if available
            func_info = f"[{record.funcName}]" if hasattr(record, 'funcName') else ''
            
            # Add these to record
            record.thread_process = f"{thread_info}{process_info}"
            record.function_info = func_info
            
            return super().format(record)
            
        def formatException(self, ei):
            """Enhanced exception formatting."""
            result = super().formatException(ei)
            return f"\nException Details:\n{result}"
    
    # Create formatters
    detailed_formatter = SafeFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)s %(thread_process)s %(function_info)s | %(message)s%(extra_data)s',
        datefmt='%Y-%m-%d %H:%M:%S.%f'
    )
    simple_formatter = SafeFormatter(
        '%(levelname)-8s | %(name)s | %(message)s'
    )
    
    # Set up console handler with UTF-8 encoding
    if sys.platform == 'win32':
        console_handler = logging.StreamHandler(sys.stdout)
    else:
        console_handler = logging.StreamHandler()
    
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # Set up file handler if log file is specified
    if log_file:
        # Use RotatingFileHandler instead of FileHandler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)

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