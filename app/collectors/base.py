from abc import ABC, abstractmethod
from app.models import NewsArticle


class BaseCollector(ABC):

    @abstractmethod
    def collect(self) -> list[NewsArticle]:
        pass