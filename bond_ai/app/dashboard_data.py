import streamlit as st
from bond.agent import Agent, AgentResponseHandler
from typing_extensions import override
import base64
import json


class Message:
    def __init__(self, content, id, type, role):
        self.content = content
        self.id = id
        self.type = type
        self.role = role

    def __str__(self) -> str:
        return f"Message: {self.id} {self.type} {self.role} -> {self.content}"


class DashboardData(AgentResponseHandler):

  def __init__(self, threads):
      self.data_agent = Agent.get_agent_by_name("Dashboard Data Analyst")
      self.threads = threads

      thread_id = None
      if 'dashboard.thread_id' in st.session_state:
          thread_id = st.session_state['dashboard.thread_id']
      else:
          thread_id = self.threads.create_thread()
          st.session_state['dashboard.thread_id'] = thread_id

      self.messages_key = f"{self.threads.user_id}-{thread_id}-messages"
      if self.messages_key not in st.session_state:
          st.session_state[self.messages_key] = self.threads.get_messages(thread_id)


  @override
  def on_content(self, content, id, type, role):

      # check if the content containts the json data which should be bookended by ```json and ```
      # somewhere within the content
      print(f"Got new content: {content}")
      if "```json" in content and "```" in content:
          json_start = content.index("```json") + 7
          json_end = content.index("```", json_start)
          print(f"Content json data from {json_start} to {json_end}")
          json_data = content[json_start:json_end]
          print(f"Content contains json data: \n\n{json_data}\n\n")
          try:
              json_obj = json.loads(json_data)
              st.session_state['dashboard.cards'] = json_obj
              print(f"Setting cards to json object")
          except Exception as e:
              print(f"Error parsing json data: {e}")
          content = content[:json_start-7] + ' ' + content[json_end+3:]

      st.session_state[self.messages_key][id] = Message(content=content, id=id, type=type, role=role)
      # self.add_message(Message(content=content, id=id, type=type, role=role))
      # self.display_chat_message(content, type, role)

  @override
  def on_done(self, success=True, message=None):
      print("Doing streamlit rerun")
      st.rerun()
  
  def display_message(self, message):
      with st.chat_message(message.role):
          if message.type == "text":
              st.markdown(message.content)
          elif message.type == "image_file":
              if isinstance(message.content, str) and message.content.startswith('data:image/png;base64,'):
                  base64_image = message.content[len('data:image/png;base64,'):]
                  image_data = base64.b64decode(base64_image)
                  st.image(image_data)
              else:
                  st.image(message.content)

  def render_card(self, key, value):
      with st.container():
          st.markdown(
              f"""
              <div style="border: 1px solid #ddd; border-radius: 10px; padding: 2px; text-align: center; background-color: #363636; margin: 2px;">
                  <p style="font-size: 12px; margin-bottom: 2px;">{key.replace('_', ' ').title()}</h4>
                  <p style="font-size: 12px; font-weight: bold;">{value:,.2f}</p>
              </div>
              """,
              unsafe_allow_html=True,
          )


  def display(self, thread_id=None):

        # if thread_id is None:
        #     if 'dashboard.thread_id' not in st.session_state:
        #         st.session_state['dashboard.thread_id'] = self.threads.create_thread()
        # else:
        #     st.session_state['dashboard.thread_id'] = thread_id

        # if 'dashboard.thread_id' not in st.session_state:
        #     st.session_state['dashboard.thread_id'] = self.threads.create_thread()

        # thread_id = st.session_state['dashboard.thread_id']
        # self.messages_key = f"{self.threads.user_id}-{thread_id}-messages"

        # if self.messages_key not in st.session_state:
        #     st.session_state[self.messages_key] = self.threads.get_messages(thread_id)
        
        left, right = st.columns(2)

        # Get the data for the Kia Center venue for January through March 2024

        with left:
          print("Showing the prompt")
          if prompt := st.chat_input("Describe your data in terms of a date range and filter criteria."):
              asst_message = self.data_agent.create_user_message(prompt, st.session_state['dashboard.thread_id'])

              message = Message(content=prompt, id=asst_message.id, type='text', role='user')
              st.session_state[self.messages_key][message.id] = message
              self.display_message(message)

              self.data_agent.handle_response(None, st.session_state['dashboard.thread_id'], self)
          else:
            for message in st.session_state[self.messages_key].values():
                self.display_message(message)

        with right:
          print("Showing the data")
          if 'dashboard.cards' in st.session_state:
              cards = st.session_state['dashboard.cards']
              keys = list(cards.keys())
              values = list(cards.values())
              cols = st.columns(3)  
              for i, (key, value) in enumerate(zip(keys, values)):
                  if not key.startswith("_"):
                    with cols[i % len(cols)]:
                        self.render_card(key, value)
          else:
              st.write("No data to display")
          # print(f"Looping thru {len(st.session_state[self.messages_key])} messages")
          # for message in st.session_state[self.messages_key].values():
          #     self.display_message(message)





