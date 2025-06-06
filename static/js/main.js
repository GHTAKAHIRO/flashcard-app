console.log("🚀 高速練習モード対応版 main.js が読み込まれました");

// ========== 練習モード高速化用変数 ==========
let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};
let isPracticeMode = false;
let prerenderedCards = [];
let practiceRoundCount = 0; // 練習ラウンド数
let totalPracticeCards = 0; // 総練習カード数

// ========== 練習完了時の視覚的フィードバック ==========
function showPracticeCompletionAnimation() {
    // 画面全体にオーバーレイを表示
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(135deg, rgba(40, 167, 69, 0.95), rgba(34, 197, 94, 0.95));
        z-index: 10000;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 24px;
        font-weight: bold;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;
    
    const content = document.createElement('div');
    content.style.cssText = `
        text-align: center;
        transform: scale(0.8);
        transition: transform 0.5s ease;
    `;
    
    content.innerHTML = `
        <div style="font-size: 4rem; margin-bottom: 1rem;">🎉</div>
        <div style="font-size: 1.8rem; margin-bottom: 0.5rem;">練習ラウンド完了！</div>
        <div style="font-size: 1.2rem; opacity: 0.9;">次の問題を準備中...</div>
        <div style="margin-top: 2rem;">
            <div class="spinner-border" role="status" style="width: 3rem; height: 3rem; border-width: 0.3rem;">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    
    overlay.appendChild(content);
    document.body.appendChild(overlay);
    
    // アニメーション開始
    requestAnimationFrame(() => {
        overlay.style.opacity = '1';
        content.style.transform = 'scale(1)';
    });
    
    return overlay;
}

function showPracticeRoundTransition(newRoundCount, newTotalCards) {
    const transition = document.createElement('div');
    transition.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(135deg, rgba(0, 123, 255, 0.95), rgba(102, 126, 234, 0.95));
        z-index: 10000;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 24px;
        font-weight: bold;
        opacity: 0;
        transition: all 0.4s ease;
    `;
    
    const content = document.createElement('div');
    content.style.cssText = `
        text-align: center;
        transform: translateY(20px);
        transition: transform 0.5s ease;
    `;
    
    content.innerHTML = `
        <div style="font-size: 4rem; margin-bottom: 1rem;">🔄</div>
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">練習ラウンド ${newRoundCount}</div>
        <div style="font-size: 1.2rem; opacity: 0.9;">${newTotalCards}問の練習を続けます</div>
        <div style="margin-top: 1rem; font-size: 1rem; opacity: 0.8;">間違えた問題を克服しましょう！</div>
    `;
    
    transition.appendChild(content);
    document.body.appendChild(transition);
    
    // アニメーション開始
    requestAnimationFrame(() => {
        transition.style.opacity = '1';
        content.style.transform = 'translateY(0)';
    });
    
    // 2秒後に削除
    setTimeout(() => {
        transition.style.opacity = '0';
        setTimeout(() => {
            transition.remove();
        }, 400);
    }, 2000);
}

// ========== カード事前取得とキャッシュ（改善版） ==========
let nextPracticeCardsCache = null;
let preloadInProgress = false;

function preloadNextPracticeCards() {
    if (!isPracticeMode || preloadInProgress) return;
    
    preloadInProgress = true;
    console.log("🔄 次の練習カードを事前取得中...");
    
    fetch(`/images_batch/${getCurrentSource()}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        preloadInProgress = false;
        
        if (data.cards && data.cards.length > 0) {
            nextPracticeCardsCache = data.cards;
            console.log("✅ 次の練習カード事前取得完了:", data.cards.length + "問");
            
            // 画像を並列プリロード（高速化）
            const imagePromises = [];
            data.cards.forEach(card => {
                if (card.image_problem) {
                    const imgPromise = new Promise((resolve) => {
                        const img = new Image();
                        img.onload = img.onerror = resolve;
                        img.src = card.image_problem;
                    });
                    imagePromises.push(imgPromise);
                }
                if (card.image_answer) {
                    const imgPromise = new Promise((resolve) => {
                        const img = new Image();
                        img.onload = img.onerror = resolve;
                        img.src = card.image_answer;
                    });
                    imagePromises.push(imgPromise);
                }
            });
            
            // すべての画像プリロード完了を待つ
            Promise.all(imagePromises).then(() => {
                console.log("🖼️ 次の練習カード画像プリロード完了");
            });
            
        } else if (data.type === 'practice_complete') {
            nextPracticeCardsCache = [];
            console.log("ℹ️ 次の練習カードなし（練習完了）");
        } else {
            nextPracticeCardsCache = [];
            console.log("ℹ️ 次の練習カードなし");
        }
    })
    .catch(error => {
        preloadInProgress = false;
        console.error("❌ 次の練習カード取得エラー:", error);
        nextPracticeCardsCache = null;
    });
}

// ========== 練習完了時の高速処理 ==========
function handlePracticeCompletionFast(cardId, result) {
    console.log("🎯 練習完了 - 高速処理開始");
    
    // 1. 完了アニメーション表示
    const overlay = showPracticeCompletionAnimation();
    
    // 2. サーバーに結果送信（高速レスポンス期待）
    fetch('/log_result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            card_id: cardId,
            result: result,
            stage: stage,
            mode: mode
        })
    }).then(response => response.json())
    .then(data => {
        console.log("📨 練習完了サーバーレスポンス:", data);
        
        setTimeout(() => {
            overlay.remove();
            
            // 🚀 高速継続フラグをチェック
            if (data.fast_continue === true && data.next_cards && data.next_cards.length > 0) {
                console.log("⚡ 高速継続: サーバーから次のカードを受信");
                
                practiceRoundCount++;
                totalPracticeCards = data.remaining_count;
                
                // サーバーから受信したカードで即座に更新
                updateCardsInstantly(data.next_cards);
                showPracticeRoundTransition(practiceRoundCount, totalPracticeCards);
                
                // 次の次のカードを事前取得
                setTimeout(() => {
                    preloadNextPracticeCards();
                }, 1000);
                
            } else if (data.practice_continuing && data.remaining_count > 0) {
                // 従来の継続処理（リロード）
                console.log("🔄 練習継続: ページリロード");
                showPracticeRoundTransition(practiceRoundCount + 1, data.remaining_count);
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
                
            } else if (data.practice_completed || data.redirect_to_prepare) {
                // 練習完了
                console.log("✅ 練習完了: 準備画面へ");
                showInstantMessage(data.message || "✅ 練習完了！");
                setTimeout(() => {
                    window.location.href = '/prepare/' + getCurrentSource();
                }, 2000);
                
            } else {
                // フォールバック
                console.log("🔧 フォールバック処理");
                handleDefaultCompletion();
            }
            
        }, 1200); // 完了アニメーション時間
        
    }).catch(error => {
        console.error("❌ 練習完了エラー:", error);
        setTimeout(() => {
            overlay.remove();
            
            // キャッシュがあれば使用、なければフォールバック
            if (nextPracticeCardsCache && nextPracticeCardsCache.length > 0) {
                console.log("🔄 エラー時キャッシュフォールバック");
                practiceRoundCount++;
                updateCardsInstantly(nextPracticeCardsCache);
                showPracticeRoundTransition(practiceRoundCount, nextPracticeCardsCache.length);
            } else {
                handleDefaultCompletion();
            }
        }, 1200);
    });
}

// ========== カード即座更新システム ==========
function updateCardsInstantly(newCards) {
    console.log("⚡ カード即座更新:", newCards.length + "問");
    
    // 古いカードを削除
    cards = newCards.slice();
    currentIndex = 0;
    showingAnswer = false;
    
    // カウンターリセット
    resetCounters();
    
    // 事前レンダリング更新
    prerenderAllCards();
    
    // 進捗更新
    updateProgressInstantly();
    
    console.log("✅ カード更新完了");
}

function resetCounters() {
    const correctSpan = document.getElementById('correct-count');
    const incorrectSpan = document.getElementById('incorrect-count');
    
    if (correctSpan) correctSpan.textContent = '0';
    if (incorrectSpan) incorrectSpan.textContent = '0';
}

// ========== 修正版完了処理 ==========
function handleCardCompletionSync(cardId, result) {
    console.log("🔧 カード完了時処理:", cardId, result);
    
    if (isPracticeMode) {
        // 練習モードは高速処理
        handlePracticeCompletionFast(cardId, result);
    } else {
        // テストモードは従来通り
        fetch('/log_result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_id: cardId,
                result: result,
                stage: stage,
                mode: mode
            })
        }).then(response => response.json())
        .then(data => {
            console.log("✅ テストモードサーバーレスポンス:", data);
            
            if (data.redirect_to_prepare === true) {
                if (data.message) {
                    showInstantMessage(data.message);
                }
                setTimeout(() => {
                    window.location.href = '/prepare/' + getCurrentSource();
                }, 2000);
            } else {
                handleDefaultCompletion();
            }
        }).catch(error => {
            console.error('❌ テストモード完了エラー:', error);
            handleDefaultCompletion();
        });
    }
}

// ========== 事前レンダリングシステム（既存） ==========
function prerenderAllCards() {
    console.log("🚀 全カード事前レンダリング開始");
    
    const flashcard = document.getElementById('flashcard');
    if (!flashcard) return;
    
    flashcard.style.position = 'relative';
    flashcard.style.overflow = 'hidden';
    flashcard.innerHTML = '';
    
    // 古い事前レンダリングカードをクリア
    prerenderedCards = [];
    
    cards.forEach(function(card, index) {
        const cardElement = createCardElement(card, index);
        flashcard.appendChild(cardElement);
        prerenderedCards.push(cardElement);
        
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
        img.loading = 'eager';
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
        answerImg.loading = 'eager';
        answerDiv.appendChild(answerImg);
    }
    
    container.appendChild(problemDiv);
    container.appendChild(answerDiv);
    
    return container;
}

// ========== 瞬間カード切り替え（既存） ==========
function switchToCardInstantly(newIndex) {
    if (newIndex >= cards.length) return false;
    
    if (prerenderedCards[currentIndex]) {
        prerenderedCards[currentIndex].style.display = 'none';
    }
    
    if (prerenderedCards[newIndex]) {
        prerenderedCards[newIndex].style.display = 'flex';
        
        const problemDiv = prerenderedCards[newIndex].querySelector('.problem-container');
        const answerDiv = prerenderedCards[newIndex].querySelector('.answer-container');
        if (problemDiv && answerDiv) {
            problemDiv.style.display = 'block';
            answerDiv.style.display = 'none';
        }
    }
    
    currentIndex = newIndex;
    showingAnswer = false;
    
    updateProgressInstantly();
    
    return true;
}

function updateProgressInstantly() {
    const progressElement = document.getElementById('progress-info');
    if (progressElement) {
        const progressText = '<i class="fas fa-chart-line"></i> ' + (currentIndex + 1) + ' / ' + cards.length;
        const roundText = isPracticeMode && practiceRoundCount > 0 ? 
            ' <span style="color: #007bff; font-weight: bold;">(ラウンド ' + practiceRoundCount + ')</span>' : '';
        progressElement.innerHTML = progressText + roundText;
    }
}

// ========== 瞬間回答処理（既存） ==========
function handleAnswerInstantly(result) {
    console.log("⚡ 瞬間回答: " + result + " (カード" + (currentIndex + 1) + "/" + cards.length + ")");
    
    const currentCardId = cards[currentIndex].id;
    
    updateCountersInstantly(result);
    triggerButtonFeedback(result);
    
    const success = switchToCardInstantly(currentIndex + 1);
    
    if (!success) {
        console.log("🏁 全カード完了");
        handleCardCompletionSync(currentCardId, result);
        return;
    }
    
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

// ========== 瞬間解答切り替え（既存） ==========
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

// ========== ログ処理（既存） ==========
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

function handleDefaultCompletion() {
    console.log("🔧 デフォルト完了処理");
    
    if (isPracticeMode) {
        showInstantMessage("問題を読み込んでいます...");
        setTimeout(function() {
            window.location.reload();
        }, 1000);
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
    console.log("🚀 高速練習モード対応版初期化開始");
    
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません");
        return;
    }
    
    cards = shuffle(rawCards.slice());
    currentIndex = 0;
    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    practiceRoundCount = isPracticeMode ? 1 : 0;
    totalPracticeCards = cards.length;
    
    console.log("📊 カードデータ: " + cards.length + "枚");
    console.log("📚 練習モード: " + isPracticeMode);
    
    prerenderAllCards();
    setupInstantEvents();
    setupInstantKeyboard();
    
    // 練習モードの場合、事前に次のカードを取得開始
    if (isPracticeMode) {
        setTimeout(() => {
            preloadNextPracticeCards();
        }, 2000);
    }
    
    console.log("🚀 高速練習モード対応版初期化完了");
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

// ========== ユーティリティ（既存） ==========
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

console.log("🚀 高速練習モード対応版 瞬間応答システム読み込み完了");