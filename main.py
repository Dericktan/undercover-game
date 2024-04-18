from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase
# from https://towardsdatascience.com/deploy-to-google-cloud-run-using-github-actions-590ecf957af0
import os
import sys
from flask import Flask, session, render_template
import ast

# from tests and from regular running of the app
CURR_DIR = os.path.dirname(os.path.abspath(__file__))
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
            room = generate_unique_code(6)
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
    name = session.get("name")
    if not name or not room:
        return
    if room not in rooms:
        leave_room(room)
        return
    join_room(room)
    send({"name":name, "message": "has joined the Game"}, to=room)
    rooms[room]["members"].append(name)

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
            rooms[room]["host"] = rooms[room]["members"][0]
            send({"name":rooms[room]["host"],"message": "is now new host"}, to=room)
            # Emitting the event when a new host is appointed
            socketio.emit("hostChange", {"isHost": rooms[room]["host"]}, room=session['room'])
    send({"name":name,"message": "has left the Game"}, to=room)

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

@socketio.on("startGame")
def startGame(data):
    room = session.get("room")
    if len(rooms[room]["members"]) < 4:
        content = {
            "name": "System",
            "message": "Minimum 4 players required to start the game."
        }
        send(content, to=room)
        return
    
    if data["data"] !="":
        setUndercover = int(data["data"])
    else:
        setUndercover = 0

    with open('words-id.txt', 'r') as file:
        words = file.readlines()
    # Select a random word from the list
    random_word = random.choice(words)
    rooms[room]["words"]=random_word

    users = rooms[room]["members"]
    rooms[room]["inGameUsers"] = {user: False for user in users}
    undercovers = random.sample(users,setUndercover)
    room_roles={}
    for user in undercovers:
        room_roles[user] = "undercover"
    
    civilians = [user for user in users if user not in undercovers]
    mrWhite = random.choice(civilians)
    civilians.remove(mrWhite)
    for user in civilians:
        room_roles[user] = "civilian"
    room_roles[mrWhite] = "white"
    rooms[room]["roles"] = room_roles
    room_roles = dict(sorted(room_roles.items()))
    socketio.emit("updateRoles", {'room_roles': room_roles, 'random_word': random_word}, room=session['room'])
    inGameUsers = list(rooms[room]["inGameUsers"].keys())
    while rooms[room]["roles"][inGameUsers[0]] == "white":
        random.shuffle(inGameUsers)
    socketio.emit("updateVotingTable",{"inGameUsers":inGameUsers},room=room)
    socketio.emit("gameStarted")
    send({
        "name": "System",
        "message": "Game Started. Check your role."
    }, to=room)


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
            if voted_for != "skip":
                if voted_for in votes_count:
                    votes_count[voted_for] += 1
                else:
                    votes_count[voted_for] = 1
        
        total_users = len(rooms[room]["inGameUsers"])
        majority_vote = total_users // 2 + 1  # Majority requires more than half of the votes
        
        # Find if any user has a majority of votes
        for user, votes in votes_count.items():
            if votes >= majority_vote:
                if rooms[room]["roles"][user] == "white":
                    roleName = "Mr. White"
                elif rooms[room]["roles"][user] == "undercover":
                    roleName = "Undercover"
                else:
                    roleName = "Civilian"
                content = {
                    "name": "System",
                    "message": user + " was voted out. "+user+" was "+roleName+"."
                }
                socketio.emit("eliminate",{"name":user},room=room)
                send(content,to=room)
                if rooms[room]["roles"][user] == "white":
                    content = {
                        "name": "System",
                        "message": "Waiting for Mr. White to guess the word."
                    }
                    send(content,to=room)
                    socketio.emit("guessWord",{"white":user},room=room)
                    return True
                    break
                del rooms[room]["inGameUsers"][user]
                rooms[room]["inGameUsers"] = {user: False for user in rooms[room]["inGameUsers"].keys()}
                inGameUsers = list(rooms[room]["inGameUsers"].keys())
                while rooms[room]["roles"][inGameUsers[0]] == "white":
                    random.shuffle(inGameUsers)
                socketio.emit("updateVotingTable",{"inGameUsers":inGameUsers},room=room)
                break
        rooms[room]["inGameUsers"] = {user: False for user in (rooms[room]["inGameUsers"]).keys()}
        remaining_roles = list(rooms[room]["roles"][user] for user in rooms[room]["inGameUsers"].keys())
        if all(role == "civilian" for role in remaining_roles):
            # All remaining players are civilians, end the game
            content = {
                "name": "System",
                "message": "All remaining players are civilians. Game Over."
            }
            send(content, to=room)
            socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"Civilian"}, room=room) 
            # Perform any other actions to end the game
            
        elif all(role == "undercover" for role in remaining_roles):
            # All remaining players are undercover, end the game
            content = {
                "name": "System",
                "message": "All remaining players are undercover. Game Over."
            }
            send(content, to=room)
            socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"Undercover"}, room=room) 
        elif len(remaining_roles) == 2:
            if remaining_roles.count("white") == 1:
                otherRole = "Undercover" if remaining_roles.count('undercover') == 1 else "Civilian"
                content = {
                    "name": "System",
                    "message": "It's a tie between Mr. White and "+otherRole+". Mr. White will try to guess the word."
                }
                send(content, to=room)
                content = {
                    "name": "System",
                    "message": "Waiting for Mr. White to guess the word."
                }
                send(content,to=room)
                whiteUser = ""
                for user in rooms[room]["inGameUsers"].keys():
                    if rooms[room]["roles"][user] == "white":
                        whiteUser = user
                        break
                socketio.emit("guessWord",{"white":whiteUser},room=room)
            else:
                if remaining_roles.count("undercover") == 1:
                    content = {
                        "name": "System",
                        "message": "Undercover won the game. Game Over."
                    }
                    send(content, to=room)
                    socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"Undercover"}, room=room)
        else:
            content = {
                "name": "System",
                "message": "Game continues..."
            }
            send(content,to=room)
            # Update the voting table and continue the game
            inGameUsers = list(rooms[room]["inGameUsers"].keys())
            inGameUsers.sort()
            socketio.emit("updateVotingTable", {"inGameUsers": inGameUsers}, room=room)

@socketio.on("guessedWord")
def guessedWord(data):
    room = session.get("room")
    name = session.get("name")
    words = ast.literal_eval(rooms[room]["words"].lower())
    if data["data"] != "" and data["data"].lower() in words:
        content = {
            "name": "System",
            "message": f"Mr. White correctly guess the word: {data}. Mr. White won the game."
        }
        send(content,to=room)
        socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":name + " also known as Mr. White"}, room=room) 
    else:
        content = {
            "name": "System",
            "message": "Mr. White incorrectly guess the word. Mr. White lost the game."
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
                "name": "System",
                "message": "All remaining players are civilians. Game Over."
            }
            send(content, to=room)
            socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"Civilian"}, room=room) 
            # Perform any other actions to end the game
            
        elif all(role == "undercover" for role in remaining_roles):
            # All remaining players are undercover, end the game
            content = {
                "name": "System",
                "message": "All remaining players are undercover. Game Over."
            }
            send(content, to=room)
            socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"Undercover"}, room=room) 

            # Perform any other actions to end the game
            
        elif remaining_roles.count("white") == 1 and len(remaining_roles) == 1:
            # Only the white player remains, end the game
            content = {
                "name": "System",
                "message": "All remaining players is Mr. White. Game Over."
            }
            send(content, to=room)
            socketio.emit("roomRoles", {"roles":rooms[room]["roles"],"winner":"Mr. White"}, room=room) 

            # Perform any other actions to end the game
        elif len(remaining_roles) < 3:
            socketio.emit("roomRoles", {"roles":rooms[room]["roles"], "winner":"Undercover"}, room=room) 
            
        else:
            # Update the voting table and continue the game
            inGameUsers = list(rooms[room]["inGameUsers"].keys())
            random.shuffle(inGameUsers)
            socketio.emit("updateVotingTable", {"inGameUsers": inGameUsers}, room=room)


if __name__ == "__main__":
    socketio.run(app,debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))