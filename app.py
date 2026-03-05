from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from secrets import token_urlsafe
import requests
from waitress import serve
from wonderwords import RandomWord

load_dotenv() 
MAILCOW_DOMAIN = os.getenv("MAILCOW_DOMAIN")
MAILCOW_API_KEY = os.getenv("MAILCOW_API_KEY")
RANDOM_WORDS_COUNT = int(os.getenv("RANDOM_WORDS_COUNT"))
RANDOM_WORDS_DELEMITER = os.getenv("RANDOM_WORDS_DELEMITER")
RANDOM_CARACTER_NBRE = int(os.getenv("RANDOM_CARACTER_NBRE"))

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
    return {prefix}, f"{prefix}@{domain}"
    
def make_alias(domain: str) -> str:
    """Return a random alias like: aBc3dE5fGh@domain.tld"""
    local = token_urlsafe(RANDOM_CARACTER_NBRE)          # url-safe, no + or /
    return {local}, f"{local}@{domain}"

@app.route('/<path:destination_email>/api/v1/aliases', methods=['POST']) 
def create_alias(destination_email):
    #Getting data
    data = request.json
    domain = data.get('domain')
    description = data.get('description')
    BRIDGE_API_KEY = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
    
    #Validation pair email:API_KEY
    if not string_in_file('/app/lookup/pair.txt', f"{destination_email}:{BRIDGE_API_KEY}"):
        return jsonify(), 401
        
    #Generating the actual alias
    local, alias = make_alias_random_words(domain)

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
    created=None
    if record is not None:
        id=pickAttr(record, "id")
        created=pickAttr(record, "created")
        updateCommentsForAlias(id, description)
        
    return jsonify({"data": {"id": local, "user_id": id,"local_part": local,"email": alias,"description": description,"created_at": created,"updated_at": created,"domain": domain}}), 201

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=6510)
