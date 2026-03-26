from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from secrets import token_urlsafe
import requests
from waitress import serve
from wonderwords import RandomWord
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
import threading

load_dotenv() 
MAILCOW_DOMAIN = os.getenv("MAILCOW_DOMAIN")
MAILCOW_API_KEY = os.getenv("MAILCOW_API_KEY")
RANDOM_WORDS_COUNT = int(os.getenv("RANDOM_WORDS_COUNT"))
RANDOM_WORDS_DELEMITER = os.getenv("RANDOM_WORDS_DELEMITER")
RANDOM_CARACTER_NBRE = int(os.getenv("RANDOM_CARACTER_NBRE"))

class Format (Enum):
    random_characters = "random_characters"
    uuid = "uuid"
    random_words = "random_words"
    random_male_name = "random_male_name"
    random_female_name = "random_female_name"
    random_noun = "random_noun"
    custom = "custom"

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

def getAllAlias():
    resp = requests.get(
    f"{MAILCOW_DOMAIN}/api/v1/get/alias/all",
    headers={
        "Content-Type": "application/json",
        "x-api-key": MAILCOW_API_KEY
    },
    timeout=10
    ) 
    if resp.status_code == 200:
        return resp.json()
    return jsonify()

def findRecordByAttr(array: str, idx: str, idxValue):
    for obj in array:
        if obj.get(idx) == idxValue:
            return obj
    return None

def pickAttr(obj: str, idx: str):
    return obj.get(idx)

def updateCommentsForAlias(id: str, public: str):
    resp = requests.post(
    f"{MAILCOW_DOMAIN}/api/v1/edit/alias",
    headers={
        "Content-Type": "application/json",
        "x-api-key": MAILCOW_API_KEY
    },
    json={
        "attr": {
            "private_comment": "ADDY",
            "public_comment": public
       },
        "items": [
            id
        ]
    },
    timeout=10
    )

def make_alias_random_words(domain: str) -> str:
    r = RandomWord()
    rw = r.random_words(RANDOM_WORDS_COUNT)
    prefix = RANDOM_WORDS_DELEMITER.join(rw)
    return f"{prefix}", f"{prefix}@{domain}"
    
def make_alias(domain: str) -> str:
    """Return a random alias like: aBc3dE5fGh@domain.tld"""
    local = token_urlsafe(RANDOM_CARACTER_NBRE)          # url-safe, no + or /
    return f"{local}", f"{local}@{domain}"

@app.route('/<path:destination_email>/api/v1/aliases', methods=['POST']) 
def create_alias(destination_email):
    #Getting data
    data = request.json
    domain = data.get('domain')
    description = data.get('description')
    format = data.get('format', "random_words")
    BRIDGE_API_KEY = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
    
    #Validation pair email:API_KEY
    if not string_in_file('/app/lookup/pair.txt', f"{destination_email}:{BRIDGE_API_KEY}"):
        return jsonify(), 401
        
    # Get current local date and time
    local_now = datetime.now()
    created = local_now.strftime("%Y-%m-%d %H:%M:%S")
        
    #Generating the actual alias
    local = ""
    alias = ""
    match Format[format]:
        case Format.random_words | Format.random_male_name | Format.random_female_name | Format.random_noun:
            local, alias = make_alias_random_words(domain)
        case Format.random_characters:
            local, alias = make_alias(domain)
        case Format.custom:
            local = data.get('local_part')
            if local is None:
                return "local_part empty", 400
            alias = f"{local}@{domain}"
        case Format.uuid:
            local = UUID.uuid4()
            alias = f"{local}@{domain}"
        case _:
            local, alias = make_alias(domain)

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
        "goto": destination_email,
        "sogo_visible": 1
    },
    timeout=10
) 
    if resp.status_code != 200:
        return jsonify(), resp.status_code

    data=getAllAlias()
    record=findRecordByAttr(data, "address", alias)
    id=None
    if record is not None:
        id=pickAttr(record, "id")
        updateCommentsForAlias(id, description)
        
    return jsonify({"data": {"id": local,
                             "user_id":destination_email,
                             "local_part":local,
                             "email": alias,
                             "description": description,
                             "attached_recipients_only": False,
                             "emails_forwarded": 0,
                             "emails_blocked": 0,
                             "emails_replied": 0,
                             "emails_sent": 0,
                             "last_forwarded": created,
                             "created_at": created,
                             "updated_at": created, 
                             "domain": domain,
                             "active":True}}
                  ), 201

@app.route('/<path:destination_email>/api/v1/aliases/<id>', methods=['PATCH'])
@app.route('/<path:destination_email>/api/v1/aliases/<id>/restore', methods=['PATCH'])
@app.route('/<path:destination_email>/api/v1/aliases/<id>', methods=['DELETE'])
@app.route('/<path:destination_email>/api/v1/aliases/<id>/forget', methods=['DELETE'])
@app.route('/<path:destination_email>/api/v1/active-aliases/<id>', methods=['DELETE'])
@app.route('/<path:destination_email>/api/v1/pinned-aliases/<id>', methods=['DELETE'])
@app.route('/<path:destination_email>/api/v1/attached-recipients-only/<id>', methods=['DELETE'])
@app.route('/<path:destination_email>/api/v1/aliases', methods=['GET'])
@app.route('/<path:destination_email>/api/v1/aliases/<id>', methods=['GET'])
@app.route('/<path:destination_email>/api/v1/active-aliases', methods=['POST']) 
@app.route('/<path:destination_email>/api/v1/pinned-aliases', methods=['POST']) 
@app.route('/<path:destination_email>/api/v1/attached-recipients-only', methods=['POST']) 
@app.route('/<path:destination_email>/api/v1/alias-recipients', methods=['POST']) 
def unsupported_requests(destination_email, id):
    return "", 405

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=6510)
