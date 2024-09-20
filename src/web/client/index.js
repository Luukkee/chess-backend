import * as chessJS from 'chess.js';
import * as chessboardJS from 'cm-chessboard';
import * as chessboardJSMarks from 'cm-chessboard/src/extensions/markers/Markers';
import * as chessboardJSPromotion from 'cm-chessboard/src/extensions/promotion-dialog/PromotionDialog';
import * as chessboardJSArrows from 'cm-chessboard/src/extensions/arrows/Arrows';
import * as nn from './src/nn_functions';

const API_URL = process.env.REACT_APP_API_URL;
//aconst API_URL = "http://localhost:5001";
let game_id = null;

async function createGame() {
    const response = await fetch(`${API_URL}/new_game/${1}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    });

    const data = await response.json();
    if (data.status === "success") {
        game_id = data.game_id;  // Store the game ID
        console.log("Game created with ID:", game_id);
        //board.setPosition(data.fen, true);  // Set the initial board position using FEN
    } else {
        console.error("Error creating game:", data.message);
    }
}

// Call this when the game starts or when a new game is created
await createGame();

function getTurnColor() {
  return (chess.turn() === 'w') ? chessboardJS.COLOR.white : chessboardJS.COLOR.black;
}

let autoPlay = false;

var chess = new chessJS.Chess()
const board = new chessboardJS.Chessboard(document.getElementById("board"), {
  position: chess.fen(),
  assetsUrl: "./assets/",
  style: {borderType: chessboardJS.BORDER_TYPE.none, pieces: {file: "pieces/standard.svg"}, animationDuration: 300},
  orientation: chessboardJS.COLOR.white,
  extensions: [
      {class: chessboardJSMarks.Markers, props: {autoMarkers: chessboardJSMarks.MARKER_TYPE.square}},
      {class: chessboardJSPromotion.PromotionDialog},
      {class: chessboardJSArrows.Arrows },
  ]
});

const changeOrientationButton = document.getElementById("flipBoardButton");
changeOrientationButton.addEventListener("click", () => {
  board.setOrientation(board.getOrientation() === chessboardJS.COLOR.white ? chessboardJS.COLOR.black : chessboardJS.COLOR.white);
  overlay.classList.toggle("hidden", true);
  setTimeout(_ => {
    flipTurn();
  }, 300);
});

const autoPlayButton = document.getElementById("autoPlayButton");
autoPlayButton.addEventListener("click", () => {
  autoPlay = !autoPlay;
  flipTurn();
});

const overlay = document.getElementById("overlay");
const gameOverText = document.getElementById("gameOverText");
const gameCodeButton = document.getElementById("gameCode");
const restartButton = document.getElementById("restartButton");

restartButton.addEventListener("click", () => {
  chess.reset();
  board.setPosition(chess.fen(), true);
  overlay.classList.toggle("hidden", true);
  flipTurn();
  createGame();
});

gameCodeButton.addEventListener("click", () => {
  navigator.clipboard.writeText(chess.pgn() + " *").then(() => {
    alert("Game code copied to clipboard!");
  });
});

function make_move(move, isEngineMove = false) {

  chess.move(move);
  board.setPosition(chess.fen(), true);
  

  if (isEngineMove) {
      // Engine move: proceed without sending to backend
      setTimeout(() => {
          flipTurn();
      }, 100);
  } else {
      // Human move: send to backend before proceeding
      sendMove(move)
          .then(() => {
              setTimeout(() => {
                  flipTurn();
              }, 100);
          })
          .catch(error => {
              console.error("Failed to send move to backend:", error);
              // Handle the error appropriately
          });
  }
}

async function makeEngineMove(chessboard) {
  const possibleMoves = chess.moves({verbose: true});

    const prediction = await nn.predictMoves(game_id);
    //const predictionPossible = prediction.filter(move => possibleMovesLan.includes(move));
    if (prediction) {
      make_move(prediction, true);
    } else {
      console.log("Bot can't make move so it will make a random move");
      make_move(possibleMoves[Math.floor(Math.random() * possibleMoves.length)], true);
    }
  }

async function flipTurn() {
  // check if the game is over
  if (chess.isCheckmate()) {
    gameOverText.innerText = chess.turn() === board.getOrientation() ? "You got checkmated!" : "You checkmated the opponent!";
    overlay.classList.toggle("hidden", false);
    return;
  }
  if (chess.isDraw()) {
    chess.loadPgn(chess.pgn() + " 1/2-1/2");
    gameOverText.innerText = "Draw = Loss here!";
    overlay.classList.toggle("hidden", false);
    return;
  }
  console.log(chess.turn());
  console.log(board.getOrientation());
  console.log(getTurnColor());
  if (getTurnColor() === board.getOrientation() && !autoPlay) {
    board.enableMoveInput(inputHandler, board.getOrientation());
  } else {
      board.disableMoveInput();
      await makeEngineMove(board);
  }
}

function sendMove(move) {
  if (!game_id) {
      console.error("No game ID available.");
      return Promise.reject("No game ID available.");
  }

  return fetch(`${API_URL}/move/${game_id}`, {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json',
      },
      body: JSON.stringify({
          move: { move: move },
      })
  })
  .then(response => response.json())
  .then(data => {
      if (data.status === "success") {
          // Move processed successfully
          return data;
      } else {
          console.error("Error making move:", data.message);
          return Promise.reject(data.message);
      }
  })
  .catch(error => {
      console.error("Error in sendMove:", error);
      return Promise.reject(error);
  });
}



function inputHandler(event) {
  if(event.type === chessboardJS.INPUT_EVENT_TYPE.movingOverSquare) {
    return
  }

  if(event.type !== chessboardJS.INPUT_EVENT_TYPE.moveInputFinished) {
    event.chessboard.removeLegalMovesMarkers();
  }
  if (event.type === chessboardJS.INPUT_EVENT_TYPE.moveInputStarted) {
    const moves = chess.moves({square: event.squareFrom, verbose: true});
    event.chessboard.addLegalMovesMarkers(moves);
    return moves.length > 0;
  }
  if (event.type === chessboardJS.INPUT_EVENT_TYPE.moveInputFinished) {
    if(event.legalMove) {
      event.chessboard.disableMoveInput();
    }
    return;
  }

  if (event.type === chessboardJS.INPUT_EVENT_TYPE.validateMoveInput) {
    const move = {from: event.squareFrom, to: event.squareTo, promotion: event.promotion};
    let result = false;

    try {
      result = chess.move(move);
      
      console.log(result);

      event.chessboard.state.moveInputProcess.then(() => {
        event.chessboard.setPosition(chess.fen(), true).then(() => {
          sendMove(move)
          .then(() => {
              setTimeout(() => {
                  flipTurn();
              }, 100);
          })
          .catch(error => {
              console.error("Failed to send move to backend:", error);
              // Handle the error appropriately
          });
          
        })
      })

    } catch (e) {
      let possibleMoves = chess.moves({square: event.squareFrom, verbose: true});

      for (const possibleMove of possibleMoves) {
        if (!possibleMove.promotion || possibleMove.to !== event.squareTo) {
          continue;
        }

        event.chessboard.showPromotionDialog(event.squareTo, chessboardJS.COLOR.white, (result) => {
          if (result.type === chessboardJSPromotion.PROMOTION_DIALOG_RESULT_TYPE.pieceSelected) {
            const move = {from: event.squareFrom, to: event.squareTo, promotion: result.piece.charAt(1)};
              
            make_move(move);
          } else {
            event.chessboard.enableMoveInput(inputHandler, event.chessboard.getOrientation());
            event.chessboard.setPosition(chess.fen(), true);
          }
        });

        return true;
      }
    }
    return result;
  }
}

board.enableMoveInput(inputHandler, chessboardJS.COLOR.white);
