console.log("🔧 シンプル修正版 main.js が読み込まれました");

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

// ========== シンプルなカード作成関数 ==========
function createCardElement(card, index) {
    const container = document.createElement('div');
    container.className = 'prerendered-card';
    container.style.cssText = 'position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 10px; box-sizing: border-box;';
    container.dataset.cardIndex = index;
    container.dataset.cardId = card.id;
    
    // 問題部分
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-container';
    problemDiv.style.cssText = 'display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; text-align: center;';
    
    if (card.image_problem) {
        const img = document.createElement('img');
        img.src = card.image_problem;
        // シンプルな画像設定：画面幅いっぱい
        img.style.cssText = 'width: 100%; max-width: 100%; height: auto; object-fit: contain; display: block; margin: 0 auto;';
        img.loading = 'eager';
        problemDiv.appendChild(img);
    }
    
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = card.problem_number + ": " + card.topic;
        text.style.cssText = 'margin: 10px 0 0 0; font-weight: bold; font-size: 16px; color: #333; word-wrap: break-word;';
        problemDiv.appendChild(text);
    }
    
    // 解答部分
    const answerDiv = document.createElement('div');
    answerDiv.className = 'answer-container';
    // 最初は確実に非表示
    answerDiv.style.cssText = 'display: none; flex-direction: column; align-items: center; justify-content: center; width: 100%; text-align: center;';
    
    if (card.image_answer) {
        const answerImg = document.createElement('img');
        answerImg.src = card.image_answer;
        // 解答画像も画面幅いっぱい
        answerImg.style.cssText = 'width: 100%; max-width: 100%; height: auto; object-fit: contain; display: block; margin: 0 auto;';
        answerImg.loading = 'eager';
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
        
        // 問題・解答の表示状態をリセット
        const problemDiv = prerenderedCards[newIndex].querySelector('.problem-container');
        const answerDiv = prerenderedCards[newIndex].querySelector('.answer-container');
        if (problemDiv && answerDiv) {
            problemDiv.style.display = 'flex';
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

// ========== 瞬間解答切り替え ==========
function toggleAnswerInstantly() {
    if (!prerenderedCards[currentIndex]) return;
    
    const problemDiv = prerenderedCards[currentIndex].querySelector('.problem-container');
    const answerDiv = prerenderedCards[currentIndex].querySelector('.answer-container');
    
    if (problemDiv && answerDiv) {
        showingAnswer = !showingAnswer;
        
        if (showingAnswer) {
            problemDiv.style.display = 'none';
            answerDiv.style.display = 'flex';
        } else {
            problemDiv.style.display = 'flex';
            answerDiv.style.display = 'none';
        }
    }
}

// ========== 瞬間回答処理 ==========
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
        handleCardCompletionSync(currentCardId, result);
        return;
    }
    
    // 4. 通常カード - 非同期ログ送信
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

// ========== ログ処理 ==========
function sendResultBackground(cardId, result) {
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

// ========== 完了処理（簡略版） ==========
function handleCardCompletionSync(cardId, result) {
    console.log("🔧 カード完了時同期処理:", cardId, result);
    
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
        
        if (data.redirect_to_prepare === true) {
            setTimeout(function() {
                window.location.href = '/prepare/' + getCurrentSource();
            }, 1000);
        } else {
            setTimeout(function() {
                window.location.href = '/prepare/' + getCurrentSource();
            }, 1000);
        }
    }).catch(function(error) {
        console.error('❌ 完了時ログエラー:', error);
        setTimeout(function() {
            window.location.href = '/prepare/' + getCurrentSource();
        }, 1000);
    });
}

// ========== 初期化 ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔧 シンプル修正版初期化開始");
    
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません");
        return;
    }
    
    cards = shuffle(rawCards.slice());
    currentIndex = 0;
    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    
    console.log("📊 カードデータ: " + cards.length + "枚");
    console.log("📚 練習モード: " + isPracticeMode);
    
    prerenderAllCards();
    setupInstantEvents();
    setupInstantKeyboard();
    
    console.log("🔧 シンプル修正版初期化完了");
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
        const temp = array[i];
        array[i] = array[j];
        array[j] = temp;
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

console.log("🔧 シンプル修正版読み込み完了");