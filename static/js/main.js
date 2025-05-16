console.log("✅ main.js 読み込まれました");

function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};  // カードIDごとの記録

function setCards(data) {
    cards = shuffle(data);
    currentIndex = 0;
    showingAnswer = false;
    renderCard();
}

function renderCard() {
    const card = cards[currentIndex];
    const cardDiv = document.getElementById('flashcard');
    cardDiv.innerHTML = '';

    const questionDiv = document.createElement('div');
    if (card.image_problem) {
        const img = document.createElement('img');
        img.src = card.image_problem;
        questionDiv.appendChild(img);
    }
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = `${card.problem_number}: ${card.topic}`;
        questionDiv.appendChild(text);
    }

    if (showingAnswer) {
        const answerDiv = document.createElement('div');
        if (card.image_answer) {
            const img = document.createElement('img');
            img.src = card.image_answer;
            answerDiv.appendChild(img);
        }
        const answerText = document.createElement('p');
        answerText.textContent = card.answer;
        answerDiv.appendChild(answerText);
        cardDiv.appendChild(answerDiv);
    } else {
        cardDiv.appendChild(questionDiv);
    }
}

function toggleAnswer() {
    showingAnswer = !showingAnswer;
    renderCard();
}

function markKnown() {
    const id = cards[currentIndex].id;
    cardStatus[id] = 'known';
    nextCard();
}

function markUnknown() {
    const id = cards[currentIndex].id;
    cardStatus[id] = 'unknown';
    nextCard();
}

function nextCard() {
    if (currentIndex + 1 >= cards.length) {
        alert("学習完了！おつかれさまでした。");
        return;
    }
    currentIndex += 1;
    showingAnswer = false;
    renderCard();
}
