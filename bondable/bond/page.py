from abc import ABC, abstractmethod



class Page(ABC):
   
  @abstractmethod
  def display(self, thread_id):
    pass

  @abstractmethod
  def get_id(self):
     pass

  @abstractmethod
  def get_name(self):
    pass

  @abstractmethod
  def get_description(self):
    pass