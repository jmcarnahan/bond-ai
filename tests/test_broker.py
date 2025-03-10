import logging 
LOGGER = logging.getLogger(__name__)

from bondable.bond.broker import Broker, BondMessage
from bondable.bond.cache import bond_cache_clear
import os
import sys
import pytest


class MessageListener:

  def __init__(self, conn):
    self.messages = []
    self.conn = conn

  def run(self):
    while True:
      message = self.conn.wait_for_message()
      if message is None:
        break
      self.messages.append(message)
      if message.is_done:
        break
    
  def start(self):
    import threading
    self.thread = threading.Thread(target=self.run)
    self.thread.start()

  def join(self):
    self.thread.join()

class TestBroker:

  def setup_method(self):
    bond_cache_clear()

  def test_cache(self):
    broker = Broker.broker()
    broker2 = Broker.broker()
    assert broker is not None
    assert broker2 is not None
    assert id(broker) == id(broker2)

  def test_sync_message_1(self):
    broker = Broker.broker()
    assert broker is not None
    
    thread_id = 'test_thread'
    conn = broker.connect(thread_id=thread_id, subscriber_id='test_subscriber')
    assert conn is not None
  
    message = BondMessage(thread_id=thread_id, message_id='test_message', type='test_type', role='test_role')
    broker.publish(thread_id, message=message.to_start_xml())
    broker.publish(thread_id, 'hello world')
    broker.publish(thread_id, message=message.to_end_xml())

    message = conn.wait_for_message()
    assert message is not None
    assert message.thread_id == thread_id
    assert message.message_id == 'test_message'
    assert message.type == 'test_type'
    assert message.role == 'test_role'
    assert message.is_error == False
    assert message.is_done == False
    assert message.clob.get_content() == 'hello world'

    broker.stop()


  def test_sync_message_2(self):
    broker = Broker.broker()
    assert broker is not None
    
    thread_id = 'test_thread'
    conn = broker.connect(thread_id=thread_id, subscriber_id='test_subscriber')
    assert conn is not None
  
    message = BondMessage(thread_id=thread_id, message_id='test_message', type='test_type', role='test_role')
    broker.publish(thread_id, message=message.to_start_xml())
    broker.publish(thread_id, 'hello world')
    broker.publish(thread_id, message=message.to_end_xml())

    message = BondMessage(thread_id=thread_id, message_id='test_message', type='test_type', role='test_role')
    broker.publish(thread_id, message=message.to_start_xml())
    broker.publish(thread_id, 'goodbye jumbo')
    broker.publish(thread_id, message=message.to_end_xml())

    message = conn.wait_for_message()
    assert message is not None
    assert message.clob.get_content() == 'hello world'

    message = conn.wait_for_message()
    assert message is not None
    assert message.clob.get_content() == 'goodbye jumbo'
    
    broker.stop()

  def test_sync_message_3(self):
    broker = Broker.broker()
    assert broker is not None
    
    thread_id = 'test_thread'
    conn_1 = broker.connect(thread_id=thread_id, subscriber_id='test_subscriber_1')
    assert conn_1 is not None
    conn_2 = broker.connect(thread_id=thread_id, subscriber_id='test_subscriber_2')
    assert conn_2 is not None

    message = BondMessage(thread_id=thread_id, message_id='test_message', type='test_type', role='test_role')
    broker.publish(thread_id, message=message.to_start_xml())
    broker.publish(thread_id, 'hello world')
    broker.publish(thread_id, message=message.to_end_xml())

    message = BondMessage(thread_id=thread_id, message_id='test_message', type='test_type', role='test_role')
    broker.publish(thread_id, message=message.to_start_xml())
    broker.publish(thread_id, 'goodbye jumbo')
    broker.publish(thread_id, message=message.to_end_xml())

    message = conn_1.wait_for_message()
    assert message is not None
    assert message.clob.get_content() == 'hello world'

    message = conn_1.wait_for_message()
    assert message is not None
    assert message.clob.get_content() == 'goodbye jumbo'

    message = conn_2.wait_for_message()
    assert message is not None
    assert message.clob.get_content() == 'hello world'

    message = conn_2.wait_for_message()
    assert message is not None
    assert message.clob.get_content() == 'goodbye jumbo'

    broker.stop()


  def test_async_message_1(self):
    broker = Broker.broker()
    assert broker is not None
    
    thread_id = 'test_thread'
    conn = broker.connect(thread_id=thread_id, subscriber_id='test_subscriber')
    assert conn is not None

    listener = MessageListener(conn)
    listener.start()

    message = BondMessage(thread_id=thread_id, message_id='test_message', type='test_type', role='test_role')
    broker.publish(thread_id, message=message.to_start_xml())
    broker.publish(thread_id, 'hello world')
    broker.publish(thread_id, message=message.to_end_xml())

    broker.stop()
    listener.join()

    assert len(listener.messages) == 1
    message = listener.messages[0]
    assert message is not None
    assert message.clob.get_content() == 'hello world'

  def test_async_message_2(self):
    broker = Broker.broker()
    assert broker is not None
    
    thread_id = 'test_thread'
    conn = broker.connect(thread_id=thread_id, subscriber_id='test_subscriber')
    assert conn is not None

    listener = MessageListener(conn)
    listener.start()

    message = BondMessage(thread_id=thread_id, message_id='test_message', type='test_type', role='test_role')
    broker.publish(thread_id, message=message.to_start_xml())
    broker.publish(thread_id, 'hello world')
    broker.publish(thread_id, message=message.to_end_xml())

    message = BondMessage(thread_id=thread_id, message_id='test_message', type='test_type', role='test_role')
    broker.publish(thread_id, message=message.to_start_xml())
    broker.publish(thread_id, 'goodbye jumbo')
    broker.publish(thread_id, message=message.to_end_xml())

    broker.stop()
    listener.join()

    assert len(listener.messages) == 2
    message = listener.messages[0]
    assert message is not None
    assert message.clob.get_content() == 'hello world'  
    message = listener.messages[1]
    assert message is not None
    assert message.clob.get_content() == 'goodbye jumbo'  

  def test_async_message_2(self):
    broker = Broker.broker()
    assert broker is not None
    
    thread_id = 'test_thread'

    conn_1 = broker.connect(thread_id=thread_id, subscriber_id='test_subscriber_1')
    assert conn_1 is not None
    listener_1 = MessageListener(conn_1)
    listener_1.start()

    conn_2 = broker.connect(thread_id=thread_id, subscriber_id='test_subscriber_2')
    assert conn_2 is not None
    listener_2 = MessageListener(conn_2)
    listener_2.start()

    message = BondMessage(thread_id=thread_id, message_id='test_message', type='test_type', role='test_role')
    broker.publish(thread_id, message=message.to_start_xml())
    broker.publish(thread_id, 'hello world')
    broker.publish(thread_id, message=message.to_end_xml())

    message = BondMessage(thread_id=thread_id, message_id='test_message', type='test_type', role='test_role')
    broker.publish(thread_id, message=message.to_start_xml())
    broker.publish(thread_id, 'goodbye jumbo')
    broker.publish(thread_id, message=message.to_end_xml())

    broker.stop()
    listener_1.join()
    listener_2.join()

    assert len(listener_1.messages) == 2
    message = listener_1.messages[0]
    assert message is not None
    assert message.clob.get_content() == 'hello world'  
    message = listener_1.messages[1]
    assert message is not None
    assert message.clob.get_content() == 'goodbye jumbo'  


    assert len(listener_2.messages) == 2
    message = listener_2.messages[0]
    assert message is not None
    assert message.clob.get_content() == 'hello world'  
    message = listener_2.messages[1]
    assert message is not None
    assert message.clob.get_content() == 'goodbye jumbo'  