from abc import ABC, abstractmethod
from typing import List, Any
from core.models import Frame

class BaseParser(ABC):
    """
    Абстрактный базовый класс для всех парсеров рамок.
    Реализует паттерн Strategy для различных алгоритмов поиска.
    """
    @abstractmethod
    def find_frames(self, doc: Any) -> List[Frame]:
        """
        Ищет рамки в текущем чертеже.
        
        :param doc: COM-объект ActiveDocument AutoCAD
        :return: Список найденных рамок (объектов Frame)
        """
        pass
