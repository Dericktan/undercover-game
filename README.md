# UnderCover Game

UnderCover Game is a multiplayer online game built using Flask, allowing users to play the classic undercover detective game online with friends.

## Features

- **Join or Create Rooms:** Players can either join existing rooms by entering a room code or create new rooms to invite friends.
- **Messaging:** Real-time messaging between players within a room.
- **Game Setup:** Hosts can set the number of undercover players before starting the game.
- **Role Assignment:** Each player gets a specific role (undercover, civilian, or Mr. White) assigned randomly.
- **Voting:** Players can vote to eliminate suspects during the game.
- **Guess Word:** Mr. White gets a chance to guess the word related to the game.

## Technologies Used

- **Python Framework:** Flask
- **Frontend:** HTML, CSS, JavaScript
- **WebSockets:** Socket.IO

## Visit the Game

[Play UnderCover Game](https://dj-undercover-42f60f4703b7.herokuapp.com/)

## Setup Instructions

1. **Clone the repository:** `git clone https://github.com/denilayush/undercover-game.git`
2. **Install dependencies:** `pip install -r requirements.txt`
3. **Start the Flask server:** `python main.py`
4. **Access the game in your web browser:** `http://127.0.0.1:8080/`

## Usage

1. [Visit the deployed game](https://dj-undercover-42f60f4703b7.herokuapp.com/) or run it locally.
2. Create a new room or join an existing room using a room code.
3. Once enough players are in the room, the host can start the game.
4. Follow the game instructions to play roles, send messages, vote, and guess the word.

## Contributing

Contributions are welcome! If you'd like to contribute to this project, please follow these steps:
1. **Fork** the project.
2. Create your feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -m 'Add new feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request.

## Acknowledgments

- [Tim Ruscica](https://github.com/techwithtim/Python-Live-Chat-App): This project significantly aided in comprehending WebSocket functionality within messaging applications. The learnings from this project were instrumental in developing the UnderCover Game.
