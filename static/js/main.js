console.log("🚀 main.js が Render 上で動いています！");

document.addEventListener('DOMContentLoaded', function () {
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません！");
        return;
    }

    document.getElementById('flashcard').addEventListener('click', toggleAnswer);
    document.getElementById('knownBtn').addEventListener('click', markKnown);
    document.getElementById('unknownBtn').addEventListener('click', markUnknown);

    isPracticeMode = typeof mode !== 'undefined' && mode === 'practice';
    initCards(rawCards);
});

let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};  // id => 'known' or 'unknown'
let wrongCards = [];
let isPracticeMode = false;

function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

function initCards(data) {
    cards = shuffle(data.slice());
    currentIndex = 0;
    showingAnswer = false;
    cardStatus = {};
    wrongCards = [];
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

    cardDiv.appendChild(questionDiv);

    if (showingAnswer && card.image_answer) {
        const answerDiv = document.createElement('div');
        const img = document.createElement('img');
        img.src = card.image_answer;
        answerDiv.appendChild(img);
        cardDiv.appendChild(answerDiv);
    }
}

function toggleAnswer() {
    showingAnswer = !showingAnswer;
    renderCard();
}

function markKnown() {
    const id = cards[currentIndex].id;
    cardStatus[id] = 'known';
    sendResult(id, 'known');
    nextCard();
}

function markUnknown() {
    const id = cards[currentIndex].id;
    cardStatus[id] = 'unknown';
    if (isPracticeMode) {
        wrongCards.push(cards[currentIndex]);
    }
    sendResult(id, 'unknown');
    nextCard();
}

function sendResult(cardId, result) {
    fetch('/log_result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ card_id: cardId, result: result })
    }).then(res => {
        if (!res.ok) {
            console.error("❌ サーバーへの記録に失敗しました");
        }
    }).catch(err => {
        console.error("エラーが発生しました:", err);
    });
}

function nextCard() {
    currentIndex++;

    if (currentIndex >= cards.length) {
        if (isPracticeMode) {
            const nextRound = wrongCards.slice();
            wrongCards = [];

            if (nextRound.length === 0) {
                alert("✅ 全問正解！練習完了！");
                window.location.href = `/prepare/${cards[0].source}`;
                return;
            }

            alert("✏️ 間違えたカードのみ再出題します！");
            cards = shuffle(nextRound);
            currentIndex = 0;
            showingAnswer = false;
            renderCard();
            return;
        } else {
            alert("✅ テスト完了！お疲れさまでした！");
            window.location.href = `/prepare/${cards[0].source}`;
            return;
        }
    }

    showingAnswer = false;
    renderCard();
}
