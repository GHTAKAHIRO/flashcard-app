console.log("🔧 画像全幅表示対応 main.js が読み込まれました");

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

// ========== 画像全幅表示対応カード作成関数 ==========
function createCardElement(card, index) {
    const container = document.createElement('div');
    container.className = 'prerendered-card';
    // 🎨 修正：パディング削除、スクロールバー削除、全幅対応
    container.style.cssText = 'position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; align-items: stretch; justify-content: center; padding: 0; box-sizing: border-box; overflow: hidden;';
    container.dataset.cardIndex = index;
    container.dataset.cardId = card.id;
    
    // 問題部分
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-container';
    // 🎨 修正：全幅に伸ばす設定
    problemDiv.style.cssText = 'display: flex; flex-direction: column; align-items: stretch; width: 100%; text-align: center; margin: 0; padding: 0;';
    
    if (card.image_problem) {
        const img = document.createElement('img');
        img.src = card.image_problem;
        // 🎨 修正：完全に画面幅いっぱいの画像設定
        img.style.cssText = 'width: 100%; max-width: 100%; height: auto; object-fit: contain; display: block; margin: 0; border: none; box-shadow: none; border-radius: 0;';
        img.loading = 'eager';
        problemDiv.appendChild(img);
    }
    
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = card.problem_number + ": " + card.topic;
        // 🎨 修正：テキストは背景付きで見やすく
        text.style.cssText = 'margin: 10px; font-weight: bold; font-size: 16px; color: #333; word-wrap: break-word; max-width: 100%; padding: 10px; line-height: 1.4; background: rgba(255,255,255,0.9); border-radius: 4px; position: relative; z-index: 1;';
        problemDiv.appendChild(text);
    }
    
    // 解答部分
    const answerDiv = document.createElement('div');
    answerDiv.className = 'answer-container';
    // 🎨 修正：解答も全幅対応
    answerDiv.style.cssText = 'display: none; flex-direction: column; align-items: stretch; width: 100%; text-align: center; margin: 0; padding: 0;';
    
    if (card.image_answer) {
        const answerImg = document.createElement('img');
        answerImg.src = card.image_answer;
        // 🎨 修正：解答画像も完全に画面幅いっぱい
        answerImg.style.cssText = 'width: 100%; max-width: 100%; height: auto; object-fit: contain; display: block; margin: 0; border: none; box-shadow: none; border-radius: 0;';
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
        
        // 問題表示状態にリセット
        const problemDiv = prerenderedCards[newIndex].querySelector('.problem-container');
        const answerDiv = prerenderedCards[newIndex].querySelector('.answer-container');
        if (problemDiv && answerDiv) {
            problemDiv.style.display = 'flex';
            problemDiv.style.flexDirection = 'column';
            problemDiv.style.alignItems = 'stretch';
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
            answerDiv.style.flexDirection = 'column';
            answerDiv.style.alignItems = 'stretch';
        } else {
            problemDiv.style.display = 'flex';
            problemDiv.style.flexDirection = 'column';
            problemDiv.style.alignItems = 'stretch';
            answerDiv.style.display = 'none';
        }
    }
}

// ========== 画像サイズ強制調整 ==========
function forceImageFullWidth() {
    console.log("🎨 画像を強制的に全幅表示に調整");
    
    // 全ての画像を取得
    const images = document.querySelectorAll('#flashcard img, .prerendered-card img');
    
    images.forEach(function(img) {
        // 強制的に全幅設定を適用
        img.style.setProperty('width', '100%', 'important');
        img.style.setProperty('max-width', '100%', 'important');
        img.style.setProperty('height', 'auto', 'important');
        img.style.setProperty('object-fit', 'contain', 'important');
        img.style.setProperty('display', 'block', 'important');
        img.style.setProperty('margin', '0', 'important');
        img.style.setProperty('border', 'none', 'important');
        img.style.setProperty('box-shadow', 'none', 'important');
        img.style.setProperty('border-radius', '0', 'important');
    });
    
    // フラッシュカードのスクロールバーも強制削除
    const flashcard = document.getElementById('flashcard');
    if (flashcard) {
        flashcard.style.setProperty('overflow', 'hidden', 'important');
        flashcard.style.setProperty('padding', '0', 'important');
    }
    
    // プリレンダリングカードのスクロールバーも強制削除
    const prerenderedCards = document.querySelectorAll('.prerendered-card');
    prerenderedCards.forEach(function(card) {
        card.style.setProperty('overflow', 'hidden', 'important');
        card.style.setProperty('padding', '0', 'important');
        card.style.setProperty('align-items', 'stretch', 'important');
    });
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

// ========== ページ遷移時のクリーンアップ ==========
window.addEventListener('beforeunload', function() {
    console.log("🧹 ページ遷移前のクリーンアップ");
    
    if (window.currentFetchController) {
        window.currentFetchController.abort();
    }
    
    if (window.redirectTimer) {
        clearTimeout(window.redirectTimer);
    }
});

// ========== 完了処理 ==========
function handleCardCompletionSync(cardId, result) {
    console.log("🔧 カード完了時同期処理:", cardId, result);
    
    disableAllButtons();
    
    const isTestMode = !isPracticeMode;
    const overlay = showCompletionOverlay("処理中...", isTestMode);
    
    const controller = new AbortController();
    window.currentFetchController = controller;
    
    fetch('/log_result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            card_id: cardId,
            result: result,
            stage: stage,
            mode: mode
        }),
        signal: controller.signal
    }).then(function(response) {
        return response.json();
    }).then(function(data) {
        console.log("✅ 完了時サーバーレスポンス:", data);
        
        if (data.redirect_to_prepare === true) {
            console.log("🎯 サーバー指示：prepare画面へリダイレクト");
            updateOverlayMessage(overlay, data.message || (isTestMode ? "テスト完了！" : "練習完了！"));
            
            window.redirectTimer = setTimeout(function() {
                window.location.href = '/prepare/' + getCurrentSource();
            }, 1500);
        } else {
            console.log("🔧 サーバー指示なし：デフォルト処理");
            handleDefaultCompletion(overlay);
        }
    }).catch(function(error) {
        if (error.name === 'AbortError') {
            console.log("📄 ページ遷移によるリクエスト中断（正常）");
            return;
        }
        
        console.error('❌ 完了時ログエラー:', error);
        updateOverlayMessage(overlay, "エラーが発生しました");
        setTimeout(function() {
            overlay.remove();
            enableAllButtons();
        }, 2000);
    }).finally(function() {
        window.currentFetchController = null;
    });
}

function updateOverlayMessage(overlay, newMessage) {
    const messageDiv = overlay.querySelector('[data-message]');
    if (messageDiv) {
        messageDiv.textContent = newMessage;
    } else {
        const contentDiv = overlay.querySelector('div > div');
        if (contentDiv) {
            const children = contentDiv.children;
            if (children.length >= 3) {
                children[2].textContent = newMessage;
            }
        }
    }
}

function disableAllButtons() {
    console.log("🔒 全ボタン無効化");
    
    const knownBtn = document.getElementById('knownBtn');
    const unknownBtn = document.getElementById('unknownBtn');
    const flashcard = document.getElementById('flashcard');
    
    if (knownBtn) {
        knownBtn.disabled = true;
        knownBtn.style.opacity = '0.5';
        knownBtn.style.cursor = 'not-allowed';
    }
    
    if (unknownBtn) {
        unknownBtn.disabled = true;
        unknownBtn.style.opacity = '0.5';
        unknownBtn.style.cursor = 'not-allowed';
    }
    
    if (flashcard) {
        flashcard.style.pointerEvents = 'none';
        flashcard.style.opacity = '0.7';
    }
}

function enableAllButtons() {
    console.log("🔓 全ボタン有効化");
    
    const knownBtn = document.getElementById('knownBtn');
    const unknownBtn = document.getElementById('unknownBtn');
    const flashcard = document.getElementById('flashcard');
    
    if (knownBtn) {
        knownBtn.disabled = false;
        knownBtn.style.opacity = '1';
        knownBtn.style.cursor = 'pointer';
    }
    
    if (unknownBtn) {
        unknownBtn.disabled = false;
        unknownBtn.style.opacity = '1';
        unknownBtn.style.cursor = 'pointer';
    }
    
    if (flashcard) {
        flashcard.style.pointerEvents = 'auto';
        flashcard.style.opacity = '1';
    }
}

function handleDefaultCompletion(existingOverlay) {
    console.log("🔧 デフォルト完了処理");
    
    disableAllButtons();
    
    let overlay = existingOverlay;
    
    if (!overlay) {
        overlay = showCompletionOverlay(isPracticeMode ? "練習ラウンド完了！" : "テスト完了！", !isPracticeMode);
    } else {
        updateOverlayMessage(overlay, isPracticeMode ? "練習ラウンド完了！" : "テスト完了！");
    }
    
    window.redirectTimer = setTimeout(function() {
        window.location.href = '/prepare/' + getCurrentSource();
    }, 1500);
}

function showCompletionOverlay(message, isTest) {
    console.log("🎉 完了オーバーレイ表示:", message);
    
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: ' + (isTest ? 'linear-gradient(135deg, rgba(0, 123, 255, 0.95), rgba(102, 126, 234, 0.95))' : 'linear-gradient(135deg, rgba(40, 167, 69, 0.95), rgba(34, 197, 94, 0.95))') + '; z-index: 10000; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; font-size: 24px; font-weight: bold; opacity: 0; transition: opacity 0.3s ease;';
    
    const content = document.createElement('div');
    content.style.cssText = 'text-align: center; transform: scale(0.8); transition: transform 0.5s ease;';
    
    const emoji = isTest ? '🎯' : '🎉';
    const subtitle = isTest ? 'テスト完了' : '練習完了';
    
    content.innerHTML = '<div style="font-size: 5rem; margin-bottom: 1rem;">' + emoji + '</div><div style="font-size: 2.5rem; margin-bottom: 1rem;">' + subtitle + '</div><div data-message style="font-size: 1.5rem; opacity: 0.9; margin-bottom: 2rem;">' + message + '</div><div style="font-size: 1.2rem; opacity: 0.8;">準備画面に戻ります...</div>';
    
    overlay.appendChild(content);
    document.body.appendChild(overlay);
    
    requestAnimationFrame(function() {
        overlay.style.opacity = '1';
        content.style.transform = 'scale(1)';
    });
    
    return overlay;
}

// ========== 画面リサイズ対応 ==========
window.addEventListener('resize', function() {
    forceImageFullWidth();
});

// ========== 初期化 ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔧 画像全幅表示対応初期化開始");
    
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
    
    // 🎨 画像の強制全幅表示（複数回実行して確実に適用）
    setTimeout(forceImageFullWidth, 100);
    setTimeout(forceImageFullWidth, 500);
    setTimeout(forceImageFullWidth, 1000);
    
    console.log("🔧 画像全幅表示対応初期化完了");
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

// ========== 強制画像調整のグローバル関数 ==========
window.forceImageFullWidth = forceImageFullWidth;

console.log("🔧 画像全幅表示対応版読み込み完了");