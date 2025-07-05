from abc import ABCMeta


class SingletonMeta(type):
    """
    A thread-safe Singleton metaclass.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


# Combined metaclass
class SingletonABCMeta(SingletonMeta, ABCMeta):
    pass
