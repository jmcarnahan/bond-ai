#!/usr/bin/env python3
"""
Script to add a message to Firestore from command line
Usage: python add_firestore_message.py "Your message here"
"""

import os
import sys
import argparse
from datetime import datetime
from google.cloud import firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
COLLECTION_NAME = "incoming_messages"
PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID")
DEFAULT_USER_ID = os.getenv("FIREBASE_USER_ID")

def add_message(content, user_id=None, thread_name=None, agent_id=None, subject=None, duration=None):
    """Add a message to Firestore"""
    # Initialize Firestore client
    print(f"Connecting to Firestore project: {PROJECT_ID}, database: {DATABASE_ID}")
    db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)
    
    # Use provided user_id or default
    user_id = user_id or DEFAULT_USER_ID
    
    # Create message document
    doc_data = {
        'userId': user_id,
        'content': content,
        'processed': False,
        'createdAt': firestore.SERVER_TIMESTAMP,
        'metadata': {
            'threadName': thread_name or f'Message from {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            'source': 'command_line'
        }
    }
    
    # Add agent ID to metadata if provided
    if agent_id:
        doc_data['metadata']['agentId'] = agent_id
    
    # Add subject to metadata if provided
    if subject:
        doc_data['metadata']['subject'] = subject
    
    # Add duration to metadata if provided
    if duration is not None:
        doc_data['metadata']['duration'] = duration
    
    print(f"\n📤 Adding message to Firestore...")
    print(f"  User ID: {user_id}")
    print(f"  Content: {content}")
    print(f"  Thread Name: {doc_data['metadata']['threadName']}")
    if agent_id:
        print(f"  Agent ID: {agent_id}")
    if subject:
        print(f"  Subject: {subject}")
    if duration is not None:
        print(f"  Banner Duration: {duration} seconds")
    else:
        print(f"  Banner Duration: 60 seconds (default)")
    
    try:
        doc_ref = db.collection(COLLECTION_NAME).add(doc_data)
        print(f"\n✅ Message added successfully!")
        print(f"  Document ID: {doc_ref[1].id}")
        return doc_ref[1].id
    except Exception as e:
        print(f"\n❌ Error adding message: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Add a message to Firestore')
    parser.add_argument('message', help='The message content to add')
    parser.add_argument('--user-id', '-u', help=f'User ID (default: {DEFAULT_USER_ID})')
    parser.add_argument('--thread-name', '-t', help='Thread name for the message')
    parser.add_argument('--agent-id', '-a', help='Agent ID to use (default: uses mobile agent from Flutter)')
    parser.add_argument('--subject', '-s', help='Subject line for the notification banner')
    parser.add_argument('--duration', '-d', type=int, help='Banner display duration in seconds (default: 60)')
    
    args = parser.parse_args()
    
    if not args.message:
        print("❌ Error: Message content is required")
        sys.exit(1)
    
    # Add the message
    doc_id = add_message(
        content=args.message,
        user_id=args.user_id,
        thread_name=args.thread_name,
        agent_id=args.agent_id,
        subject=args.subject,
        duration=args.duration
    )
    
    if doc_id:
        print(f"\n🎉 Message added to Firestore collection '{COLLECTION_NAME}'")
        print("The Flutter app should detect and process this message automatically.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()