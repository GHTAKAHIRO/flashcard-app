console.log("🚀 main.js が Render 上で動いています！");

document.addEventListener('DOMContentLoaded', function () {
    console.log("🌐 DOMContentLoaded 発火");

    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません！");
        return;  // ここで止めてクラッシュを防ぐ
    }

    console.log("📦 rawCards:", rawCards);

    document.getElementById('flashcard').addEventListener('click', toggleAnswer);
    document.getElementById('knownBtn').addEventListener('click', markKnown);
    document.getElementById('unknownBtn').addEventListener('click', markUnknown);

    setCards(rawCards);
});

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
let cardStatus = {};

function sendResultToServer(cardId, result) {
    const payload = { card_id: cardId, result: result };
    console.log("送信するデータ：", JSON.stringify(payload));  // ✅ 文字列で出力して確認しやすく

    fetch('/log_result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)  // ✅ 同じオブジェクトを送信
    })
    .then(res => {
        if (!res.ok) {
            console.error("❌ サーバーへの記録に失敗しました");
        } else {
            console.log("✅ サーバーへの記録成功");
        }
    })
    .catch(err => {
        console.error("エラーが発生しました:", err);
    });
}
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
    console.log("🟢 knownボタン押下: id =", id);
    cardStatus[id] = 'known';
    sendResultToServer(id, 'known');
    nextCard();
}

function markUnknown() {
    const id = cards[currentIndex].id;
    cardStatus[id] = 'unknown';
    sendResultToServer(id, 'unknown');
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
