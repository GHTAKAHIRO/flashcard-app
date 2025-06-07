console.log("🔧 問題・解答分離修正版 main.js が読み込まれました");

// ========== 瞬間応答用変数 ==========
let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};
let isPracticeMode = false;
let prerenderedCards = []; // 事前レンダリング済みカード

// ========== 事前レンダリングシステム（修正版） ==========
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

// ========== 修正版カード作成関数（問題・解答分離強化） ==========
function createCardElement(card, index) {
    const container = document.createElement('div');
    container.className = 'prerendered-card';
    container.dataset.cardIndex = index;
    container.dataset.cardId = card.id;
    
    // 問題部分（必ず表示）
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-container';
    problemDiv.dataset.section = 'problem';
    
    if (card.image_problem) {
        const img = document.createElement('img');
        img.src = card.image_problem;
        img.loading = 'eager';
        img.alt = '問題画像';
        problemDiv.appendChild(img);
    }
    
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = card.problem_number + ": " + card.topic;
        problemDiv.appendChild(text);
    }
    
    // 解答部分（必ず非表示で開始）
    const answerDiv = document.createElement('div');
    answerDiv.className = 'answer-container';
    answerDiv.dataset.section = 'answer';
    // 🔥 重要：解答は必ず非表示で開始
    answerDiv.style.display = 'none !important';
    answerDiv.style.visibility = 'hidden';
    answerDiv.style.opacity = '0';
    
    if (card.image_answer) {
        const answerImg = document.createElement('img');
        answerImg.src = card.image_answer;
        answerImg.loading = 'eager';
        answerImg.alt = '解答画像';
        answerDiv.appendChild(answerImg);
    }
    
    container.appendChild(problemDiv);
    container.appendChild(answerDiv);
    
    return container;
}

// ========== 修正版カード切り替え（問題・解答状態リセット強化） ==========
function switchToCardInstantly(newIndex) {
    if (newIndex >= cards.length) return false;
    
    // 現在のカードを完全に非表示
    if (prerenderedCards[currentIndex]) {
        prerenderedCards[currentIndex].style.display = 'none';
    }
    
    // 新しいカードを表示
    if (prerenderedCards[newIndex]) {
        prerenderedCards[newIndex].style.display = 'flex';
        
        // 🔥 重要：問題・解答の表示状態を強制リセット
        const problemDiv = prerenderedCards[newIndex].querySelector('.problem-container');
        const answerDiv = prerenderedCards[newIndex].querySelector('.answer-container');
        
        if (problemDiv && answerDiv) {
            // 問題を確実に表示
            problemDiv.style.display = 'flex';
            problemDiv.style.visibility = 'visible';
            problemDiv.style.opacity = '1';
            
            // 解答を確実に非表示
            answerDiv.style.display = 'none';
            answerDiv.style.visibility = 'hidden';
            answerDiv.style.opacity = '0';
            
            console.log(`📝 カード${newIndex + 1}: 問題表示、解答非表示に設定`);
        }
    }
    
    currentIndex = newIndex;
    showingAnswer = false; // 🔥 重要：フラグもリセット
    
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

// ========== 修正版解答切り替え（状態管理強化） ==========
function toggleAnswerInstantly() {
    if (!prerenderedCards[currentIndex]) return;
    
    const problemDiv = prerenderedCards[currentIndex].querySelector('.problem-container');
    const answerDiv = prerenderedCards[currentIndex].querySelector('.answer-container');
    
    if (problemDiv && answerDiv) {
        showingAnswer = !showingAnswer;
        
        if (showingAnswer) {
            // 解答を表示、問題を非表示
            problemDiv.style.display = 'none';
            problemDiv.style.visibility = 'hidden';
            problemDiv.style.opacity = '0';
            
            answerDiv.style.display = 'flex';
            answerDiv.style.visibility = 'visible';
            answerDiv.style.opacity = '1';
            
            console.log("👁️ 解答表示モード");
        } else {
            // 問題を表示、解答を非表示
            problemDiv.style.display = 'flex';
            problemDiv.style.visibility = 'visible';
            problemDiv.style.opacity = '1';
            
            answerDiv.style.display = 'none';
            answerDiv.style.visibility = 'hidden';
            answerDiv.style.opacity = '0';
            
            console.log("📝 問題表示モード");
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

// ========== デバッグ機能（修正版） ==========
function debugStatus() {
    console.log("=== デバッグ情報 ===");
    console.log("カード数:", cards.length);
    console.log("現在のインデックス:", currentIndex);
    console.log("解答表示中:", showingAnswer);
    console.log("プリレンダリングカード数:", prerenderedCards.length);
    
    // 現在表示中のカードの詳細状態
    if (prerenderedCards[currentIndex]) {
        const currentCard = prerenderedCards[currentIndex];
        const problemDiv = currentCard.querySelector('.problem-container');
        const answerDiv = currentCard.querySelector('.answer-container');
        
        console.log("現在のカード表示状態:", {
            card_display: currentCard.style.display,
            problem_display: problemDiv ? problemDiv.style.display : "not found",
            problem_visibility: problemDiv ? problemDiv.style.visibility : "not found",
            answer_display: answerDiv ? answerDiv.style.display : "not found",
            answer_visibility: answerDiv ? answerDiv.style.visibility : "not found",
            showingAnswer_flag: showingAnswer
        });
        
        // 画像要素の確認
        const problemImg = problemDiv ? problemDiv.querySelector('img') : null;
        const answerImg = answerDiv ? answerDiv.querySelector('img') : null;
        
        console.log("画像表示状態:", {
            problem_img_visible: problemImg ? problemImg.offsetParent !== null : false,
            answer_img_visible: answerImg ? answerImg.offsetParent !== null : false,
            problem_img_src: problemImg ? problemImg.src : "なし",
            answer_img_src: answerImg ? answerImg.src : "なし"
        });
    }
}

// ========== 初期化（修正版） ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔧 問題・解答分離修正版初期化開始");
    
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません");
        return;
    }
    
    cards = shuffle(rawCards.slice());
    currentIndex = 0;
    showingAnswer = false; // 🔥 重要：初期状態は必ず問題表示
    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    
    console.log("📊 カードデータ: " + cards.length + "枚");
    console.log("📚 練習モード: " + isPracticeMode);
    
    prerenderAllCards();
    setupInstantEvents();
    setupInstantKeyboard();
    
    // 初期表示状態を確実に設定
    setTimeout(function() {
        if (prerenderedCards[0]) {
            const problemDiv = prerenderedCards[0].querySelector('.problem-container');
            const answerDiv = prerenderedCards[0].querySelector('.answer-container');
            
            if (problemDiv && answerDiv) {
                problemDiv.style.display = 'flex';
                problemDiv.style.visibility = 'visible';
                problemDiv.style.opacity = '1';
                
                answerDiv.style.display = 'none';
                answerDiv.style.visibility = 'hidden';
                answerDiv.style.opacity = '0';
                
                console.log("🎯 初期表示状態確認完了: 問題表示、解答非表示");
            }
        }
        
        // デバッグ情報を表示
        debugStatus();
    }, 500);
    
    console.log("🔧 問題・解答分離修正版初期化完了");
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

// デバッグ用グローバル関数
window.debugStatus = debugStatus;

console.log("🔧 問題・解答分離修正版読み込み完了");