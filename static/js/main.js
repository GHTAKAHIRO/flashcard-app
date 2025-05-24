// ✅ mode = 'test' or 'practice' は Flask 側から index.html に渡される
// 例: <script>const studyMode = "{{ mode }}";</script>

console.log("🚀 main.js 読み込み完了");

// グローバル変数
let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};  // id -> 'known' | 'unknown'
let wrongCards = [];  // 練習モードで使う

// 初期化
window.onload = function () {
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が未定義");
        return;
    }
    console.log("✅ studyMode:", studyMode);

    document.getElementById('flashcard').addEventListener('click', toggleAnswer);
    document.getElementById('knownBtn').addEventListener('click', markKnown);
    document.getElementById('unknownBtn').addEventListener('click', markUnknown);

    if (studyMode === 'practice') {
        initPracticeMode(rawCards);
    } else {
        initTestMode(rawCards);
    }
};

function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

// ✅ テストモード：1回出題のみ
function initTestMode(data) {
    cards = shuffle(data);
    currentIndex = 0;
    cardStatus = {};
    renderCard();
}

// ✅ 練習モード：ループ形式
function initPracticeMode(data) {
    wrongCards = [...data];
    nextPracticeRound();
}

function nextPracticeRound() {
    if (wrongCards.length === 0) {
        alert("🎉 全問正解！練習モード終了");
        window.location.href = `/prepare/${rawCards[0].source}`;
        return;
    }
    cards = shuffle(wrongCards);
    wrongCards = [];  // 今ラウンドでミスしたものを再格納
    currentIndex = 0;
    cardStatus = {};  // 今回ラウンドの成否
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

    if (showingAnswer && card.image_answer) {
        const answerDiv = document.createElement('div');
        const img = document.createElement('img');
        img.src = card.image_answer;
        answerDiv.appendChild(img);
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
    sendResultToServer(id, 'known');
    moveNext();
}

function markUnknown() {
    const id = cards[currentIndex].id;
    cardStatus[id] = 'unknown';
    sendResultToServer(id, 'unknown');
    if (studyMode === 'practice') {
        wrongCards.push(cards[currentIndex]);  // ✕のみ次ラウンド対象に
    }
    moveNext();
}

function moveNext() {
    if (currentIndex + 1 >= cards.length) {
        if (studyMode === 'practice') {
            nextPracticeRound();
        } else {
            alert("✅ テスト完了！");
            window.location.href = `/prepare/${cards[0].source}`;
        }
        return;
    }
    currentIndex++;
    showingAnswer = false;
    renderCard();
}

function sendResultToServer(cardId, result) {
    fetch('/log_result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ card_id: cardId, result: result })
    }).then(res => {
        if (!res.ok) console.error("❌ サーバー記録失敗");
    }).catch(err => console.error("❌ fetch エラー", err));
}
