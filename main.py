from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase
# from https://towardsdatascience.com/deploy-to-google-cloud-run-using-github-actions-590ecf957af0
import os
import sys
from flask import Flask, session, render_template

# from tests and from regular running of the app
CURR_DIR = os.path.dirname(os.path.abspath(__file__))
print(CURR_DIR)
sys.path.append(CURR_DIR)
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
socketio = SocketIO(app)

rooms = {}

def generate_unique_code(Length):
    while True:
        code = ""
        for _ in range(Length):
            code+= random.choice(ascii_uppercase)
        if code not in rooms:
            break
    return code

@app.route("/",methods=["POST","GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join",False)
        create = request.form.get("create",False)
        if not name:
            return render_template("home.html",error="Please enter a name.", code = code, name = name)
        if join != False and not code:
            return render_template("home.html",error="Please enter a room code.", code = code, name = name)
        
        room = code
        if create != False:
            room = generate_unique_code(8)
            rooms[room] = {"members":[name],"messages":[],"host":name,"roles":[]}
        elif code not in rooms:
            return render_template("home.html",error="Room not exists.", code = code, name = name)
        elif name in rooms[room]["members"]:
            return render_template("home.html",error="Name already taken in the room", code = code, name = name)
        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))
    
    return render_template("home.html")

@app.route("/room")
def room():
    room = session.get("room")
    name = session.get("name")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home",error="Enter correct details"))
    is_host = False
    if session.get("name") == rooms[room]["host"]:
        is_host= True
    return render_template("room.html" , code=room, is_host=is_host,name = name)

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not name or not room:
        return
    if room not in rooms:
        leave_room(room)
        return
    
    join_room(room)
    send({"name":name, "message": "has joined the Game"}, to=room)
    rooms[room]["members"].append(name)
    print(f"{name} joined Game {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)
    if room in rooms:
        rooms[room]['members'].remove(name)
        if len(rooms[room]["members"])<=0:
            del rooms[room]
        elif rooms[room]["host"] == name:
            rooms[room]["host"] = rooms[room]["members"][1]
            send({"name":rooms[room]["host"],"message": "is now new host"}, to=room)
            # Emitting the event when a new host is appointed
            socketio.emit("hostChange", {"isHost": True}, room=session['room'])
    send({"name":name,"message": "has left the Game"}, to=room)
    print(f"{name} left room {room}")

@socketio.on("message")
def message(data):
    room = session.get("room")
    name = session.get("name")
    if room not in rooms:
        return
    content = {
        "name": name,
        "message": data["data"]
    }
    send(content,to = room)
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} message: {data['data']}")

@socketio.on("startGame")
def startGame():
    room = session.get("room")
    with open('words.txt', 'r') as file:
        words = file.readlines()
    # Select a random word from the list
    random_word = random.choice(words)
    # print(random_word)

    users = rooms[room]["members"]
    undercovers = random.sample(users,2)
    room_roles={}
    for user in undercovers:
        room_roles[user] = "undercover"
    
    civilians = [user for user in users if user not in undercovers]
    mrWhite = random.choice(civilians)
    room_roles[mrWhite] = "white"
    civilians.remove(mrWhite)
    for user in civilians:
        room_roles[user] = "civilian"
    print(room_roles)
    rooms[room]["roles"] = room_roles
    socketio.emit("updateRoles", {'room_roles': room_roles, 'random_word': random_word}, room=session['room'])

if __name__ == "__main__":
    socketio.run(app,debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))