console.log("🚀 main.js が Render 上で動いています！");

document.addEventListener('DOMContentLoaded', function () {
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません！");
        return;
    }

    document.getElementById('flashcard').addEventListener('click', toggleAnswer);
    document.getElementById('knownBtn').addEventListener('click', markKnown);
    document.getElementById('unknownBtn').addEventListener('click', markUnknown);

    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    initCards(rawCards);
});

let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};  // id => 'known' or 'unknown'
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
        img.style.maxWidth = '100%';
        img.style.height = 'auto';
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
        img.style.maxWidth = '100%';
        img.style.height = 'auto';
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
}

function markUnknown() {
    const id = cards[currentIndex].id;
    cardStatus[id] = 'unknown';
    sendResult(id, 'unknown');
}

// 🔥 修正：新しいバックエンド仕様に対応したsendResult関数
async function sendResult(cardId, result) {
    try {
        console.log('[SUBMIT] 回答送信開始:', cardId, result, 'mode:', mode);
        
        const response = await fetch('/log_result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_id: cardId,
                result: result,
                stage: stage,
                mode: mode
            })
        });

        const data = await response.json();
        console.log('[SUBMIT] レスポンス受信:', data);

        if (data.status === 'ok') {
            // 🔥 テストモード完了判定
            if (data.chunk_test_completed || data.stage_test_completed) {
                console.log('[SUBMIT] テスト完了:', data);
                
                if (data.redirect_to_prepare) {
                    console.log('[SUBMIT] prepare画面に戻ります');
                    showMessage(data.message);
                    setTimeout(() => {
                        const currentSource = getCurrentSource();
                        window.location.href = `/prepare/${currentSource}`;
                    }, 2000);
                    return;
                }
            }
            
            // 🔥 練習モード完了判定
            if (data.practice_completed) {
                console.log('[SUBMIT] 練習完了:', data);
                
                if (data.redirect_to_prepare) {
                    console.log('[SUBMIT] prepare画面に戻ります');
                    showMessage(data.message);
                    setTimeout(() => {
                        const currentSource = getCurrentSource();
                        window.location.href = `/prepare/${currentSource}`;
                    }, 2000);
                    return;
                }
            }
            
            // 🔥 練習モード継続判定
            if (data.practice_continuing) {
                console.log('[SUBMIT] 練習継続:', data.remaining_count, '問残り');
                showMessage(data.message);
                
                // 🔥 重要：prepare画面に戻らず、次の問題へ
                setTimeout(() => {
                    nextCard();
                }, 1000);
                return;
            }
            
            // 🔥 通常の次の問題へ（テストモード）
            console.log('[SUBMIT] 通常の次問題へ');
            nextCard();
            
        } else {
            throw new Error(data.message || '回答の送信に失敗しました');
        }

    } catch (error) {
        console.error('[SUBMIT] エラー:', error);
        showMessage("❌ サーバーへの記録に失敗しました", "error");
        nextCard(); // エラーでも次に進む
    }
}

// 🔥 メッセージ表示関数
function showMessage(message, type = "info") {
    console.log('[MESSAGE]', type, ':', message);
    
    // 既存のメッセージを削除
    const existingMessage = document.getElementById('messageAlert');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // メッセージ要素を作成
    const messageDiv = document.createElement('div');
    messageDiv.id = 'messageAlert';
    messageDiv.className = `alert alert-${type === 'error' ? 'danger' : 'info'} alert-dismissible fade show position-fixed`;
    messageDiv.style.cssText = `
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 9999;
        min-width: 300px;
        text-align: center;
    `;
    
    messageDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(messageDiv);
    
    // 5秒後に自動削除
    setTimeout(() => {
        if (messageDiv && messageDiv.parentNode) {
            messageDiv.remove();
        }
    }, 5000);
}

// 🔥 現在のソース名を取得
function getCurrentSource() {
    // URLから教材名を取得 (例: /study/JOYFUL → JOYFUL)
    const pathParts = window.location.pathname.split('/');
    const source = pathParts[pathParts.length - 1];
    console.log('[SOURCE] 現在の教材:', source);
    return source;
}

// 🔥 修正版nextCard関数
function nextCard() {
    currentIndex++;

    // 🔥 練習モードでは、カードがなくなってもprepare画面に戻らない
    // バックエンドが適切に新しいカードを提供するまで待機
    if (currentIndex >= cards.length) {
        console.log('[NEXTCARD] カード終了:', currentIndex, '/', cards.length);
        
        if (isPracticeMode) {
            // 🔥 練習モードでカードが終了した場合
            console.log('[NEXTCARD] 練習モード - サーバーから新しいカードを待機');
            showMessage("問題を読み込んでいます...");
            
            // 🔥 ページをリロードして新しいカードを取得
            setTimeout(() => {
                window.location.reload();
            }, 1000);
            return;
        } else {
            // 🔥 テストモードでカードが終了した場合
            console.log('[NEXTCARD] テストモード完了 - prepare画面に戻る');
            showMessage("✅ テスト完了！");
            setTimeout(() => {
                const currentSource = getCurrentSource();
                window.location.href = `/prepare/${currentSource}`;
            }, 2000);
            return;
        }
    }

    showingAnswer = false;
    renderCard();
}