from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from secrets import token_urlsafe
import requests
from waitress import serve

load_dotenv() 
MAILCOW_DOMAIN = os.getenv("MAILCOW_DOMAIN")
app = Flask(__name__)

def string_in_file(file_path, search_string):
    """
    Check if a string exists in a file.
    Returns True if found, False otherwise.
    """
    # Validate file existence
    if not os.path.isfile(file_path):
        return False
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            for line_number, line in enumerate(file, start=1):
                if search_string in line:
                    return True
        return False
    except Exception as e:
        return False


def make_alias(domain: str, bytes: int = 16) -> str:
    """Return a random alias like: aBc3dE5fGh@domain.tld"""
    local = token_urlsafe(bytes)          # url-safe, no + or /
    return f"{local}@{domain}"

@app.route('/<path:destination_email>/api/v1/aliases', methods=['POST']) 
def create_alias(destination_email):
    #Getting data
    data = request.json
    domain = data.get('domain')
    MAILCOW_API_KEY = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
    #Generating the actual alias
    alias = make_alias(domain)

    # Making the actual request

    resp = requests.post(
    f"{MAILCOW_DOMAIN}/api/v1/add/alias",
    headers={
        "Content-Type": "application/json",
        "x-api-key": MAILCOW_API_KEY
    },
    json={
        "active": 1,
        "address": alias,
        "goto": destination_email
    },
    timeout=10
) 
    

    return jsonify({"data": {"email": alias}}), 201

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=6510)
