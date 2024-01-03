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
# print(CURR_DIR)
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
            room = generate_unique_code(4)
            rooms[room] = {"members":[],"messages":[],"host":name,"roles":[],"words": ""}
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
    # print(rooms)
    name = session.get("name")
    if not name or not room:
        return
    if room not in rooms:
        leave_room(room)
        return
    join_room(room)
    send({"name":name, "message": "has joined the Game"}, to=room)
    rooms[room]["members"].append(name)
    # print(rooms)
    # print(f"{name} joined Game {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    # print(rooms)
    name = session.get("name")
    leave_room(room)
    if room in rooms:
        rooms[room]['members'].remove(name)
        if len(rooms[room]["members"])<=0:
            del rooms[room]
        elif rooms[room]["host"] == name:
            rooms[room]["host"] = rooms[room]["members"][0]
            send({"name":rooms[room]["host"],"message": "is now new host"}, to=room)
            # Emitting the event when a new host is appointed
            socketio.emit("hostChange", {"isHost": rooms[room]["host"]}, room=session['room'])
    send({"name":name,"message": "has left the Game"}, to=room)
    # print(rooms)
    # print(f"{name} left room {room}")

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
    # print(f"{session.get('name')} message: {data['data']}")

@socketio.on("startGame")
def startGame(data):
    room = session.get("room")
    if data["data"] !="":
        setUndercover = int(data["data"])
    else:
        setUndercover = 0

    with open('words.txt', 'r') as file:
        words = file.readlines()
    # Select a random word from the list
    random_word = random.choice(words)
    rooms[room]["words"]=random_word
    # # print(random_word)

    users = rooms[room]["members"]
    rooms[room]["inGameUsers"] = {user: False for user in users}
    undercovers = random.sample(users,setUndercover)
    room_roles={}
    for user in undercovers:
        room_roles[user] = "undercover"
    
    civilians = [user for user in users if user not in undercovers]
    mrWhite = random.choice(civilians)
    civilians.remove(mrWhite)
    # print("White is",mrWhite)
    for user in civilians:
        room_roles[user] = "civilian"
    room_roles[mrWhite] = "white"
    # print(room_roles)
    rooms[room]["roles"] = room_roles
    room_roles = dict(sorted(room_roles.items()))
    socketio.emit("updateRoles", {'room_roles': room_roles, 'random_word': random_word}, room=session['room'])
    inGameUsers = list(rooms[room]["inGameUsers"].keys())
    # print("before",inGameUsers)
    while rooms[room]["roles"][inGameUsers[0]] == "white":
        random.shuffle(inGameUsers)
    # print("after",inGameUsers)
    # print(inGameUsers)
    socketio.emit("updateVotingTable",{"inGameUsers":inGameUsers},room=room)


@socketio.on("userVote")
def userVote(data):
    name = session.get("name")
    room = session.get("room")
    rooms[room]["inGameUsers"][name]= data
    content = {
        "name": name,
        "message": "Voted for "+data
    }
    send(content, to=room)
    all_voted = not any(value == False for value in rooms.get(room, {}).get("inGameUsers", {}).values())
    if all_voted:
        votes_count = {}
        for voter, voted_for in rooms[room]["inGameUsers"].items():
            if voted_for in votes_count:
                votes_count[voted_for] += 1
            else:
                votes_count[voted_for] = 1
        
        total_users = len(rooms[room]["inGameUsers"])
        majority_vote = total_users // 2 + 1  # Majority requires more than half of the votes
        
        # Find if any user has a majority of votes
        for user, votes in votes_count.items():
            if votes >= majority_vote:
                content = {
                    "name": "Eliminated",
                    "message": user
                }
                socketio.emit("eliminate",{"name":user},room=room)
                send(content,to=room)
                content = {
                    "name": user,
                    "message": "was "+rooms[room]["roles"][user]
                }
                send(content,to=room)
                if rooms[room]["roles"][user] == "white":
                    content = {
                    "name": "Game",
                    "message": "wait for white to guess the word"
                    }
                    send(content,to=room)
                    socketio.emit("guessWord",{"white":user},room=room)
                    break
                del rooms[room]["inGameUsers"][user]
                rooms[room]["inGameUsers"] = {user: False for user in rooms[room]["inGameUsers"].keys()}
                inGameUsers = list(rooms[room]["inGameUsers"].keys())
                # print("before",inGameUsers)
                while rooms[room]["roles"][inGameUsers[0]] == "white":
                    random.shuffle(inGameUsers)
                # print("after",inGameUsers)
                # print(inGameUsers)
                socketio.emit("updateVotingTable",{"inGameUsers":inGameUsers},room=room)
                break 
        rooms[room]["inGameUsers"] = {user: False for user in (rooms[room]["inGameUsers"]).keys()}
    remaining_roles = list(rooms[room]["roles"][user] for user in rooms[room]["inGameUsers"].keys())
    if all(role == "civilian" for role in remaining_roles):
        # All remaining players are civilians, end the game
        content = {
            "name": "Game",
            "message": "All remaining players are civilians. Game Over."
        }
        send(content, to=room)
        socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"Civilians"}, room=room) 
        # Perform any other actions to end the game
        
    elif all(role == "undercover" for role in remaining_roles):
        # All remaining players are undercover, end the game
        content = {
            "name": "Game",
            "message": "All remaining players are undercover. Game Over."
        }
        send(content, to=room)
        socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"UnderCovers"}, room=room) 

        # Perform any other actions to end the game
        
    elif remaining_roles.count("white") == 1 and len(remaining_roles) == 1:
        # Only the white player remains, end the game
        content = {
            "name": "Game",
            "message": "Only the white player remains. Game Over."
        }
        send(content, to=room)
        socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"Mr. White"}, room=room) 

        # Perform any other actions to end the game
    elif len(remaining_roles) < 3:
        socketio.emit("roomRoles", {"roles":rooms[room]["roles"], "winner":"UnderCover or White"}, room=room) 
        
    else:
        # Update the voting table and continue the game
        inGameUsers = list(rooms[room]["inGameUsers"].keys())
        inGameUsers.sort()
        # socketio.emit("updateVotingTable", {"inGameUsers": inGameUsers}, room=room)

    # print(session.get("name"))
    # print(data)

@socketio.on("guessedWord")
def guessedWord(data):
    # print("Guessed word emit.io.call")
    room = session.get("room")
    name = session.get("name")
    # print(rooms[room]["words"])
    import ast
    words = ast.literal_eval(rooms[room]["words"].lower())
    # print(words)
    if data["data"] != "" and data["data"].lower() in words:
        content = {
                    "name": "Game",
                    "message": f"White Wins; guess: {data}"
                    }
        send(content,to=room)
        socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"Mr. white:"+name}, room=room) 
    else:
        content = {
                    "name": "Game",
                    "message": "White guessed Wrong Word"
                    }
        send(content,to=room)
        del rooms[room]["inGameUsers"][data["name"]]
        rooms[room]["inGameUsers"] = {user: False for user in rooms[room]["inGameUsers"].keys()}
        inGameUsers = list(rooms[room]["inGameUsers"].keys())
        inGameUsers.sort()
        # socketio.emit("updateVotingTable",{"inGameUsers":inGameUsers},room=room)

        remaining_roles = list(rooms[room]["roles"][user] for user in rooms[room]["inGameUsers"].keys())
        if all(role == "civilian" for role in remaining_roles):
            # All remaining players are civilians, end the game
            content = {
                "name": "Game",
                "message": "All remaining players are civilians. Game Over."
            }
            send(content, to=room)
            socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"Civilians"}, room=room) 
            # Perform any other actions to end the game
            
        elif all(role == "undercover" for role in remaining_roles):
            # All remaining players are undercover, end the game
            content = {
                "name": "Game",
                "message": "All remaining players are undercover. Game Over."
            }
            send(content, to=room)
            socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"UnderCovers"}, room=room) 

            # Perform any other actions to end the game
            
        elif remaining_roles.count("white") == 1 and len(remaining_roles) == 1:
            # Only the white player remains, end the game
            content = {
                "name": "Game",
                "message": "Only the white player remains. Game Over."
            }
            send(content, to=room)
            socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"Mr. White"}, room=room) 

            # Perform any other actions to end the game
        elif len(remaining_roles) < 3:
            socketio.emit("roomRoles", {"roles":rooms[room]["roles"], "winner":"UnderCover or White"}, room=room) 
            
        else:
            # Update the voting table and continue the game
            inGameUsers = list(rooms[room]["inGameUsers"].keys())
            random.shuffle(inGameUsers)
            socketio.emit("updateVotingTable", {"inGameUsers": inGameUsers}, room=room)


if __name__ == "__main__":
    socketio.run(app,debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))