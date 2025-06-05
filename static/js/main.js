console.log("🔧 エラー修正版 main.js が読み込まれました");

// ========== グローバル関数定義（HTMLから呼び出される） ==========
// HTMLテンプレートで onclick="toggleAnswer()" が使われている可能性があるため

window.toggleAnswer = function() {
    console.log("🔄 解答切り替え (グローバル)");
    toggleAnswerFunction();
};

window.markKnown = function() {
    console.log("✅ 〇ボタンクリック (グローバル)");
    handleAnswer('known');
};

window.markUnknown = function() {
    console.log("❌ ×ボタンクリック (グローバル)");
    handleAnswer('unknown');
};

// ========== メイン変数 ==========
let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};
let isPracticeMode = false;

// ========== 安全な要素取得 ==========
function safeGetElement(id) {
    const element = document.getElementById(id);
    if (!element) {
        console.warn(`⚠️ 要素が見つかりません: ${id}`);
    }
    return element;
}

// ========== 初期化 ==========
document.addEventListener('DOMContentLoaded', function () {
    console.log("🚀 DOM読み込み完了");
    
    // デバッグ情報
    console.log("=== デバッグ情報 ===");
    console.log("rawCards:", typeof rawCards !== 'undefined' ? rawCards.length : 'undefined');
    console.log("mode:", typeof mode !== 'undefined' ? mode : 'undefined');
    console.log("stage:", typeof stage !== 'undefined' ? stage : 'undefined');
    console.log("==================");
    
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません！");
        return;
    }

    console.log(`📊 カードデータ: ${rawCards.length}枚`);

    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    console.log("📚 練習モード:", isPracticeMode);
    
    initCards(rawCards);
    setupKeyboard();
    setupClickEvents();
    
    console.log('✅ 初期化完了');
});

// ========== クリックイベント設定 ==========
function setupClickEvents() {
    console.log("🖱️ クリックイベント設定");
    
    // 既存のonclick属性を削除して新しいイベントリスナーを追加
    const flashcard = safeGetElement('flashcard');
    const knownBtn = safeGetElement('knownBtn');
    const unknownBtn = safeGetElement('unknownBtn');
    
    if (flashcard) {
        flashcard.removeAttribute('onclick');
        flashcard.addEventListener('click', function(e) {
            console.log("🎴 フラッシュカードクリック");
            toggleAnswerFunction();
        });
    }
    
    if (knownBtn) {
        knownBtn.removeAttribute('onclick');
        knownBtn.addEventListener('click', function(e) {
            console.log("✅ 〇ボタンクリック");
            handleAnswer('known');
        });
    }
    
    if (unknownBtn) {
        unknownBtn.removeAttribute('onclick');
        unknownBtn.addEventListener('click', function(e) {
            console.log("❌ ×ボタンクリック");
            handleAnswer('unknown');
        });
    }
}

// ========== カード初期化 ==========
function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

function initCards(data) {
    console.log("🔄 カード初期化開始");
    
    cards = shuffle(data.slice());
    currentIndex = 0;
    showingAnswer = false;
    cardStatus = {};
    
    console.log(`📝 シャッフル完了: ${cards.length}枚`);
    
    renderCard();
}

// ========== カードレンダリング ==========
function renderCard() {
    console.log(`🎴 カードレンダリング: ${currentIndex + 1}/${cards.length}`);
    
    const card = cards[currentIndex];
    const cardDiv = safeGetElement('flashcard');
    
    if (!cardDiv) {
        console.error("❌ flashcard要素が見つかりません");
        return;
    }
    
    if (!card) {
        console.error("❌ カードデータがありません");
        return;
    }
    
    console.log("📄 表示カード:", card);
    
    // DOM更新
    cardDiv.innerHTML = '';

    const questionDiv = document.createElement('div');
    questionDiv.id = 'problem-container';
    questionDiv.style.cssText = 'display: block; width: 100%; text-align: center;';
    
    if (card.image_problem) {
        console.log("🖼️ 問題画像:", card.image_problem);
        const img = document.createElement('img');
        img.src = card.image_problem;
        img.style.cssText = 'max-width: 100%; height: auto; display: block; margin: 0 auto; border-radius: 8px;';
        img.alt = '問題画像';
        
        img.onload = () => console.log("✅ 問題画像読み込み完了");
        img.onerror = () => console.error("❌ 問題画像読み込み失敗");
        
        questionDiv.appendChild(img);
    }
    
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = `${card.problem_number}: ${card.topic}`;
        text.style.cssText = 'margin: 10px 0; font-weight: bold; text-align: center; color: #333;';
        questionDiv.appendChild(text);
    }

    cardDiv.appendChild(questionDiv);

    // 解答部分も準備
    if (card.image_answer) {
        const answerDiv = document.createElement('div');
        answerDiv.id = 'answer-container';
        answerDiv.style.cssText = `display: ${showingAnswer ? 'block' : 'none'}; width: 100%; text-align: center;`;
        
        const answerImg = document.createElement('img');
        answerImg.src = card.image_answer;
        answerImg.style.cssText = 'max-width: 100%; height: auto; display: block; margin: 0 auto; border-radius: 8px;';
        answerImg.alt = '解答画像';
        answerDiv.appendChild(answerImg);
        
        cardDiv.appendChild(answerDiv);
    }
    
    // 進捗更新
    updateProgress();
    
    console.log("✅ カードレンダリング完了");
}

// ========== 解答切り替え ==========
function toggleAnswerFunction() {
    console.log("🔄 解答切り替え実行");
    
    showingAnswer = !showingAnswer;
    
    const problemContainer = safeGetElement('problem-container');
    const answerContainer = safeGetElement('answer-container');
    
    if (problemContainer && answerContainer) {
        if (showingAnswer) {
            problemContainer.style.display = 'none';
            answerContainer.style.display = 'block';
            console.log("👁️ 解答表示");
        } else {
            problemContainer.style.display = 'block';
            answerContainer.style.display = 'none';
            console.log("❓ 問題表示");
        }
    } else {
        console.error("❌ 解答切り替え要素が見つかりません");
        console.log("problemContainer:", problemContainer);
        console.log("answerContainer:", answerContainer);
    }
}

// ========== 回答処理 ==========
function handleAnswer(result) {
    console.log(`📝 回答処理開始: ${result}`);
    
    const id = cards[currentIndex].id;
    cardStatus[id] = result;
    
    // カウンター更新
    updateCounters(result);
    
    // ボタンフィードバック
    const button = result === 'known' ? safeGetElement('knownBtn') : safeGetElement('unknownBtn');
    if (button) {
        button.style.transform = 'scale(0.95)';
        button.style.backgroundColor = result === 'known' ? '#45a049' : '#da190b';
        
        setTimeout(() => {
            button.style.transform = 'scale(1)';
            setTimeout(() => {
                button.style.backgroundColor = '';
            }, 100);
        }, 150);
    }
    
    // サーバーに送信
    sendResult(id, result);
}

function updateCounters(result) {
    const correctSpan = safeGetElement('correct-count');
    const incorrectSpan = safeGetElement('incorrect-count');
    
    if (result === 'known' && correctSpan) {
        const current = parseInt(correctSpan.textContent) || 0;
        correctSpan.textContent = current + 1;
        console.log(`✅ 正解カウンター: ${current + 1}`);
    } else if (result === 'unknown' && incorrectSpan) {
        const current = parseInt(incorrectSpan.textContent) || 0;
        incorrectSpan.textContent = current + 1;
        console.log(`❌ 不正解カウンター: ${current + 1}`);
    }
}

function updateProgress() {
    const progressElement = safeGetElement('progress-info');
    if (progressElement) {
        progressElement.innerHTML = `<i class="fas fa-chart-line"></i> ${currentIndex + 1} / ${cards.length}`;
    }
}

// ========== サーバー通信 ==========
async function sendResult(cardId, result) {
    try {
        console.log('[SUBMIT] 回答送信開始:', cardId, result);
        
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
            handleServerResponse(data);
        } else {
            throw new Error(data.message || '回答の送信に失敗しました');
        }

    } catch (error) {
        console.error('[SUBMIT] エラー:', error);
        showMessage("❌ サーバーへの記録に失敗しました", "error");
        nextCard(); // エラーでも次に進む
    }
}

function handleServerResponse(data) {
    // 完了判定
    if (data.chunk_test_completed || data.stage_test_completed) {
        console.log('[SUBMIT] テスト完了:', data);
        
        if (data.redirect_to_prepare) {
            console.log('[SUBMIT] prepare画面に戻ります');
            showMessage(data.message);
            setTimeout(() => {
                window.location.href = `/prepare/${getCurrentSource()}`;
            }, 2000);
            return;
        }
    }
    
    if (data.practice_completed) {
        console.log('[SUBMIT] 練習完了:', data);
        
        if (data.redirect_to_prepare) {
            console.log('[SUBMIT] prepare画面に戻ります');
            showMessage(data.message);
            setTimeout(() => {
                window.location.href = `/prepare/${getCurrentSource()}`;
            }, 2000);
            return;
        }
    }
    
    if (data.practice_continuing) {
        console.log('[SUBMIT] 練習継続:', data.remaining_count, '問残り');
        showMessage(data.message);
        
        setTimeout(() => {
            nextCard();
        }, 1000);
        return;
    }
    
    // 通常の次の問題へ
    console.log('[SUBMIT] 通常の次問題へ');
    setTimeout(() => {
        nextCard();
    }, 500); // 少し遅延を入れて確実に
}

function nextCard() {
    console.log("➡️ 次のカードへ");
    
    currentIndex++;

    if (currentIndex >= cards.length) {
        console.log('[NEXTCARD] カード終了:', currentIndex, '/', cards.length);
        
        if (isPracticeMode) {
            console.log('[NEXTCARD] 練習モード - リロード');
            showMessage("問題を読み込んでいます...");
            
            setTimeout(() => {
                window.location.reload();
            }, 1000);
            return;
        } else {
            console.log('[NEXTCARD] テストモード完了');
            showMessage("✅ テスト完了！");
            setTimeout(() => {
                window.location.href = `/prepare/${getCurrentSource()}`;
            }, 2000);
            return;
        }
    }

    showingAnswer = false;
    renderCard();
}

// ========== ユーティリティ ==========
function showMessage(message, type = "info") {
    console.log('[MESSAGE]', type, ':', message);
    
    const existingMessage = document.getElementById('messageAlert');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.id = 'messageAlert';
    messageDiv.textContent = message;
    messageDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? '#f44336' : '#4CAF50'};
        color: white;
        padding: 12px 20px;
        border-radius: 6px;
        font-weight: bold;
        z-index: 1000;
        transform: translateX(100%);
        transition: transform 0.3s ease;
    `;
    
    document.body.appendChild(messageDiv);
    
    setTimeout(() => {
        messageDiv.style.transform = 'translateX(0)';
    }, 100);
    
    setTimeout(() => {
        messageDiv.style.transform = 'translateX(100%)';
        setTimeout(() => messageDiv.remove(), 300);
    }, 3000);
}

function getCurrentSource() {
    const pathParts = window.location.pathname.split('/');
    const source = pathParts[pathParts.length - 1];
    console.log('[SOURCE] 現在の教材:', source);
    return source;
}

// ========== キーボードショートカット ==========
function setupKeyboard() {
    console.log("⌨️ キーボードショートカット設定");
    
    document.addEventListener('keydown', (e) => {
        console.log("⌨️ キー押下:", e.key);
        
        switch(e.key.toLowerCase()) {
            case 'j':
            case 'arrowleft':
                e.preventDefault();
                console.log("⌨️ J/左矢印 → 〇");
                handleAnswer('known');
                break;
            case 'f':
            case 'arrowright':
                e.preventDefault();
                console.log("⌨️ F/右矢印 → ×");
                handleAnswer('unknown');
                break;
            case ' ':
                e.preventDefault();
                console.log("⌨️ Space → 解答切り替え");
                toggleAnswerFunction();
                break;
        }
    });
}

console.log('🔧 エラー修正版 main.js 読み込み完了');