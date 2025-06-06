console.log("🔧 最終修正版 瞬間応答 main.js が読み込まれました");

// ========== 瞬間応答用変数 ==========
let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};
let isPracticeMode = false;
let prerenderedCards = []; // 事前レンダリング済みカード

// ========== 事前レンダリングシステム ==========
function prerenderAllCards() {
    console.log("🚀 全カード事前レンダリング開始");
    
    const flashcard = document.getElementById('flashcard');
    if (!flashcard) return;
    
    // フラッシュカードを相対配置に
    flashcard.style.position = 'relative';
    flashcard.style.overflow = 'hidden';
    flashcard.innerHTML = '';
    
    // 全カードを事前に作成
    cards.forEach(function(card, index) {
        const cardElement = createCardElement(card, index);
        flashcard.appendChild(cardElement);
        prerenderedCards.push(cardElement);
        
        // 最初のカード以外は非表示
        if (index !== 0) {
            cardElement.style.display = 'none';
        }
    });
    
    console.log("✅ 事前レンダリング完了: " + cards.length + "枚");
}

function createCardElement(card, index) {
    const container = document.createElement('div');
    container.className = 'prerendered-card';
    container.style.cssText = 'position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;';
    container.dataset.cardIndex = index;
    container.dataset.cardId = card.id;
    
    // 問題部分
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-container';
    problemDiv.style.cssText = 'display: block; width: 100%; text-align: center;';
    
    if (card.image_problem) {
        const img = document.createElement('img');
        img.src = card.image_problem;
        img.style.cssText = 'max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);';
        img.loading = 'eager'; // 即座読み込み
        problemDiv.appendChild(img);
    }
    
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = card.problem_number + ": " + card.topic;
        text.style.cssText = 'margin: 15px 0 0 0; font-weight: bold; font-size: 16px; color: #333;';
        problemDiv.appendChild(text);
    }
    
    // 解答部分
    const answerDiv = document.createElement('div');
    answerDiv.className = 'answer-container';
    answerDiv.style.cssText = 'display: none; width: 100%; text-align: center;';
    
    if (card.image_answer) {
        const answerImg = document.createElement('img');
        answerImg.src = card.image_answer;
        answerImg.style.cssText = 'max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);';
        answerImg.loading = 'eager'; // 即座読み込み
        answerDiv.appendChild(answerImg);
    }
    
    container.appendChild(problemDiv);
    container.appendChild(answerDiv);
    
    return container;
}

// ========== 瞬間カード切り替え ==========
function switchToCardInstantly(newIndex) {
    if (newIndex >= cards.length) return false;
    
    // 現在のカードを非表示
    if (prerenderedCards[currentIndex]) {
        prerenderedCards[currentIndex].style.display = 'none';
    }
    
    // 新しいカードを表示
    if (prerenderedCards[newIndex]) {
        prerenderedCards[newIndex].style.display = 'flex';
        
        // 問題表示状態にリセット
        const problemDiv = prerenderedCards[newIndex].querySelector('.problem-container');
        const answerDiv = prerenderedCards[newIndex].querySelector('.answer-container');
        if (problemDiv && answerDiv) {
            problemDiv.style.display = 'block';
            answerDiv.style.display = 'none';
        }
    }
    
    currentIndex = newIndex;
    showingAnswer = false;
    
    // 進捗更新
    updateProgressInstantly();
    
    return true;
}

function updateProgressInstantly() {
    const progressElement = document.getElementById('progress-info');
    if (progressElement) {
        progressElement.innerHTML = '<i class="fas fa-chart-line"></i> ' + (currentIndex + 1) + ' / ' + cards.length;
    }
}

// ========== 瞬間回答処理（最終修正版） ==========
function handleAnswerInstantly(result) {
    console.log("⚡ 瞬間回答: " + result + " (カード" + (currentIndex + 1) + "/" + cards.length + ")");
    
    // 現在のカードIDを保存
    const currentCardId = cards[currentIndex].id;
    
    // 1. 瞬間カウンター更新
    updateCountersInstantly(result);
    
    // 2. 瞬間ボタンフィードバック
    triggerButtonFeedback(result);
    
    // 3. 瞬間次カード表示 or 完了
    const success = switchToCardInstantly(currentIndex + 1);
    
    if (!success) {
        console.log("🏁 全カード完了");
        // 🔧 修正：完了時は必ずサーバーレスポンスを待つ
        handleCardCompletionSync(currentCardId, result);
        return;
    }
    
    // 4. 通常カード - 非同期ログ送信（レスポンス無視）
    sendResultBackground(currentCardId, result);
}

function updateCountersInstantly(result) {
    const correctSpan = document.getElementById('correct-count');
    const incorrectSpan = document.getElementById('incorrect-count');
    
    if (result === 'known' && correctSpan) {
        const current = parseInt(correctSpan.textContent) || 0;
        correctSpan.textContent = current + 1;
    } else if (result === 'unknown' && incorrectSpan) {
        const current = parseInt(incorrectSpan.textContent) || 0;
        incorrectSpan.textContent = current + 1;
    }
}

function triggerButtonFeedback(result) {
    const button = result === 'known' ? 
        document.getElementById('knownBtn') : 
        document.getElementById('unknownBtn');
    
    if (button) {
        button.style.transform = 'scale(0.95)';
        button.style.backgroundColor = result === 'known' ? '#45a049' : '#da190b';
        
        requestAnimationFrame(function() {
            button.style.transform = 'scale(1)';
            setTimeout(function() {
                button.style.backgroundColor = '';
            }, 80);
        });
    }
}

// ========== 瞬間解答切り替え ==========
function toggleAnswerInstantly() {
    if (!prerenderedCards[currentIndex]) return;
    
    const problemDiv = prerenderedCards[currentIndex].querySelector('.problem-container');
    const answerDiv = prerenderedCards[currentIndex].querySelector('.answer-container');
    
    if (problemDiv && answerDiv) {
        showingAnswer = !showingAnswer;
        
        if (showingAnswer) {
            problemDiv.style.display = 'none';
            answerDiv.style.display = 'block';
        } else {
            problemDiv.style.display = 'block';
            answerDiv.style.display = 'none';
        }
    }
}

// ========== 最終修正版ログ処理 ==========
function sendResultBackground(cardId, result) {
    // 🔧 非同期ログ送信（レスポンス処理なし）
    fetch('/log_result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            card_id: cardId,
            result: result,
            stage: stage,
            mode: mode
        })
    }).catch(function(error) {
        console.error('非同期ログエラー:', error);
    });
}

function handleCardCompletionSync(cardId, result) {
    console.log("🔧 カード完了時同期処理:", cardId, result);
    
    // 🔧 修正：完了時は必ずサーバーレスポンスを待ってから処理
    fetch('/log_result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            card_id: cardId,
            result: result,
            stage: stage,
            mode: mode
        })
    }).then(function(response) {
        return response.json();
    }).then(function(data) {
        console.log("✅ 完了時サーバーレスポンス:", data);
        
        // 🔧 修正：サーバーからの指示に従う
        if (data.redirect_to_prepare === true) {
            console.log("🎯 サーバー指示：prepare画面へリダイレクト");
            if (data.message) {
                showInstantMessage(data.message);
            }
            setTimeout(function() {
                window.location.href = '/prepare/' + getCurrentSource();
            }, 2000);
        } else {
            console.log("🔧 サーバー指示なし：デフォルト処理");
            handleDefaultCompletion();
        }
    }).catch(function(error) {
        console.error('❌ 完了時ログエラー:', error);
        handleDefaultCompletion();
    });
}

function handleDefaultCompletion() {
    console.log("🔧 デフォルト完了処理");
    
    if (isPracticeMode) {
        // 🚀 練習モードも必ずprepare画面に戻る（シンプル化）
        showInstantMessage("✅ 練習ラウンド完了！");
        setTimeout(function() {
            window.location.href = '/prepare/' + getCurrentSource();
        }, 1500);
    } else {
        showInstantMessage("✅ テスト完了！");
        setTimeout(function() {
            window.location.href = '/prepare/' + getCurrentSource();
        }, 2000);
    }
}

function showInstantMessage(message) {
    console.log("💬 メッセージ表示:", message);
    
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #4CAF50; color: white; padding: 12px 20px; border-radius: 6px; font-weight: bold; z-index: 1000; transform: translateX(100%); transition: transform 0.3s ease;';
    
    document.body.appendChild(toast);
    
    requestAnimationFrame(function() {
        toast.style.transform = 'translateX(0)';
    });
    
    setTimeout(function() {
        toast.style.transform = 'translateX(100%)';
        setTimeout(function() {
            toast.remove();
        }, 300);
    }, 2000);
}

// ========== 初期化 ==========
document.addEventListener('DOMContentLoaded', function () {
    console.log("🔧 最終修正版初期化開始");
    
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません");
        return;
    }
    
    // カード準備
    cards = shuffle(rawCards.slice());
    currentIndex = 0;
    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    
    console.log("📊 カードデータ: " + cards.length + "枚");
    console.log("📚 練習モード: " + isPracticeMode);
    
    // 事前レンダリング
    prerenderAllCards();
    
    // イベント設定
    setupInstantEvents();
    setupInstantKeyboard();
    
    console.log("🔧 最終修正版初期化完了");
});

function setupInstantEvents() {
    const knownBtn = document.getElementById('knownBtn');
    const unknownBtn = document.getElementById('unknownBtn');
    const flashcard = document.getElementById('flashcard');
    
    if (knownBtn) {
        knownBtn.removeAttribute('onclick');
        knownBtn.addEventListener('click', function() {
            handleAnswerInstantly('known');
        });
    }
    
    if (unknownBtn) {
        unknownBtn.removeAttribute('onclick');
        unknownBtn.addEventListener('click', function() {
            handleAnswerInstantly('unknown');
        });
    }
    
    if (flashcard) {
        flashcard.removeAttribute('onclick');
        flashcard.addEventListener('click', function() {
            toggleAnswerInstantly();
        });
    }
}

function setupInstantKeyboard() {
    document.addEventListener('keydown', function(e) {
        switch(e.key.toLowerCase()) {
            case 'j':
            case 'arrowleft':
                e.preventDefault();
                handleAnswerInstantly('known');
                break;
            case 'f':
            case 'arrowright':
                e.preventDefault();
                handleAnswerInstantly('unknown');
                break;
            case ' ':
                e.preventDefault();
                toggleAnswerInstantly();
                break;
        }
    });
}

// ========== ユーティリティ ==========
function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

function getCurrentSource() {
    const pathParts = window.location.pathname.split('/');
    return pathParts[pathParts.length - 1];
}

// ========== グローバル関数（互換性） ==========
window.toggleAnswer = function() {
    toggleAnswerInstantly();
};

window.markKnown = function() {
    handleAnswerInstantly('known');
};

window.markUnknown = function() {
    handleAnswerInstantly('unknown');
};

console.log("🔧 最終修正版 瞬間応答システム読み込み完了");