import time
import random
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)

def exponential_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
) -> Callable:
    """
    Декоратор для реализации экспоненциального backoff с поддержкой jitter
    
    Args:
        max_retries: Максимальное количество попыток
        base_delay: Начальная задержка в секундах
        max_delay: Максимальная задержка в секундах
        exponential_base: База для экспоненциального роста
        jitter: Использовать ли случайное отклонение для предотвращения thundering herd
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            retries = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"Превышено максимальное количество попыток ({max_retries}). Последняя ошибка: {str(e)}")
                        raise
                    
                    # Вычисляем задержку
                    delay = min(base_delay * (exponential_base ** (retries - 1)), max_delay)
                    
                    # Добавляем случайное отклонение если включен jitter
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(f"Попытка {retries} из {max_retries} не удалась. "
                                f"Ожидание {delay:.2f} секунд перед следующей попыткой. "
                                f"Ошибка: {str(e)}")
                    
                    time.sleep(delay)
            
        return wrapper
    return decorator
