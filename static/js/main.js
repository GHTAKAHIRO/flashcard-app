console.log("🔧 シンプルレイアウト版 main.js が読み込まれました");

// ========== 瞬間応答用変数 ==========
let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};
let isPracticeMode = false;
let prerenderedCards = []; // 事前レンダリング済みカード

// ========== 画像読み込み状況を追跡 ==========
let imageLoadTracker = {
    totalImages: 0,
    loadedImages: 0,
    failedImages: 0,
    imageStatus: {} // 各画像の詳細状況
};

// ========== シンプルな事前レンダリングシステム ==========
function prerenderAllCards() {
    console.log("🚀 シンプル事前レンダリング開始");
    
    const flashcard = document.getElementById('flashcard');
    if (!flashcard) return;
    
    // フラッシュカードの基本設定
    flashcard.style.position = 'relative';
    flashcard.innerHTML = '';
    
    // 画像読み込み状況をリセット
    imageLoadTracker = { totalImages: 0, loadedImages: 0, failedImages: 0, imageStatus: {} };
    
    // 全カードを事前に作成
    cards.forEach(function(card, index) {
        const cardElement = createSimpleCardElement(card, index);
        flashcard.appendChild(cardElement);
        prerenderedCards.push(cardElement);
        
        // 最初のカードのみ表示
        if (index === 0) {
            cardElement.style.display = 'flex';
            console.log(`🎯 カード1を初期表示に設定`);
        } else {
            cardElement.style.display = 'none';
        }
    });
    
    console.log("✅ シンプル事前レンダリング完了: " + cards.length + "枚");
    console.log("📸 画像読み込み状況: 総数=" + imageLoadTracker.totalImages);
}

// ========== シンプルなカード作成関数 ==========
function createSimpleCardElement(card, index) {
    const container = document.createElement('div');
    container.className = 'prerendered-card';
    container.dataset.cardIndex = index;
    container.dataset.cardId = card.id;
    
    const cardNumber = index + 1;
    
    // 問題部分
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-container';
    problemDiv.dataset.section = 'problem';
    problemDiv.dataset.cardNumber = cardNumber;
    
    // 🔥 シンプル初期設定：最初のカードのみ表示
    if (index === 0) {
        problemDiv.style.display = 'flex';
    } else {
        problemDiv.style.display = 'none';
    }
    
    // 問題テキスト（画像の前に配置）
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = card.problem_number + ": " + card.topic;
        problemDiv.appendChild(text);
    }
    
    // 問題画像
    if (card.image_problem) {
        const img = createSimpleImageElement(card.image_problem, '問題画像', cardNumber, 'problem');
        problemDiv.appendChild(img);
        imageLoadTracker.totalImages++;
    }
    
    // 解答部分（初期状態：必ず非表示）
    const answerDiv = document.createElement('div');
    answerDiv.className = 'answer-container';
    answerDiv.dataset.section = 'answer';
    answerDiv.dataset.cardNumber = cardNumber;
    answerDiv.style.display = 'none'; // シンプル非表示
    
    // 解答画像
    if (card.image_answer) {
        const answerImg = createSimpleImageElement(card.image_answer, '解答画像', cardNumber, 'answer');
        answerDiv.appendChild(answerImg);
        imageLoadTracker.totalImages++;
    }
    
    container.appendChild(problemDiv);
    container.appendChild(answerDiv);
    
    return container;
}

// ========== シンプルな画像要素作成関数 ==========
function createSimpleImageElement(src, alt, cardNumber, type) {
    const img = document.createElement('img');
    
    const imageId = `card${cardNumber}_${type}`;
    
    // 基本属性設定
    img.src = src;
    img.alt = alt;
    img.loading = 'eager';
    img.id = imageId;
    
    // 🔥 シンプルなスタイル設定（CSSに委任）
    // JavaScriptでの強制スタイル設定を最小限に
    
    // データ属性
    img.dataset.cardNumber = cardNumber;
    img.dataset.imageType = type;
    img.dataset.originalSrc = src;
    
    // 画像状況を初期化
    imageLoadTracker.imageStatus[imageId] = {
        cardNumber: cardNumber,
        type: type,
        src: src,
        loaded: false,
        failed: false,
        visible: false
    };
    
    // 読み込み成功イベント
    img.onload = function() {
        imageLoadTracker.loadedImages++;
        imageLoadTracker.imageStatus[imageId].loaded = true;
        
        console.log(`✅ 画像読み込み成功: ${imageId} (${imageLoadTracker.loadedImages}/${imageLoadTracker.totalImages})`);
        console.log(`📐 画像サイズ: ${this.naturalWidth}x${this.naturalHeight}`);
        
        // 表示状況確認
        setTimeout(function() {
            checkSimpleImageVisibility(img, cardNumber, type);
        }, 100);
    };
    
    // 読み込み失敗イベント
    img.onerror = function() {
        imageLoadTracker.failedImages++;
        imageLoadTracker.imageStatus[imageId].failed = true;
        
        console.error(`❌ 画像読み込み失敗: ${imageId} - ${src}`);
        
        // エラー時の代替表示
        this.style.backgroundColor = '#f8f9fa';
        this.style.border = '2px dashed #dee2e6';
        this.style.minHeight = '200px';
        this.style.display = 'flex';
        this.style.alignItems = 'center';
        this.style.justifyContent = 'center';
        
        const errorDiv = document.createElement('div');
        errorDiv.textContent = `画像読み込みエラー: ${alt}`;
        errorDiv.style.textAlign = 'center';
        errorDiv.style.color = '#6c757d';
        errorDiv.style.fontSize = '14px';
        this.parentNode.appendChild(errorDiv);
    };
    
    return img;
}

// ========== シンプルなカード切り替え ==========
function switchToCardInstantly(newIndex) {
    if (newIndex >= cards.length) return false;
    
    console.log(`🔄 シンプルカード切り替え: ${currentIndex + 1} → ${newIndex + 1}`);
    
    // 現在のカードを非表示
    if (prerenderedCards[currentIndex]) {
        prerenderedCards[currentIndex].style.display = 'none';
        console.log(`👻 カード${currentIndex + 1}を非表示`);
    }
    
    // 新しいカードを表示
    if (prerenderedCards[newIndex]) {
        const newCard = prerenderedCards[newIndex];
        newCard.style.display = 'flex';
        
        // 🔥 シンプルな状態リセット
        const problemDiv = newCard.querySelector('.problem-container');
        const answerDiv = newCard.querySelector('.answer-container');
        
        if (problemDiv && answerDiv) {
            // 問題を表示、解答を非表示
            problemDiv.style.display = 'flex';
            answerDiv.style.display = 'none';
            
            console.log(`📝 カード${newIndex + 1}: 問題表示、解答非表示`);
        }
        
        console.log(`👁️ カード${newIndex + 1}を表示`);
    }
    
    currentIndex = newIndex;
    showingAnswer = false; // フラグリセット
    
    updateProgressInstantly();
    
    return true;
}

// ========== シンプルな解答切り替え ==========
function toggleAnswerInstantly() {
    if (!prerenderedCards[currentIndex]) return;
    
    const currentCard = prerenderedCards[currentIndex];
    const problemDiv = currentCard.querySelector('.problem-container');
    const answerDiv = currentCard.querySelector('.answer-container');
    
    if (problemDiv && answerDiv) {
        showingAnswer = !showingAnswer;
        
        console.log(`🔄 シンプル解答切り替え: ${showingAnswer ? '問題→解答' : '解答→問題'} (カード${currentIndex + 1})`);
        
        if (showingAnswer) {
            // 🔥 シンプル解答表示：問題非表示、解答表示
            problemDiv.style.display = 'none';
            answerDiv.style.display = 'flex';
            
            console.log("👁️ 解答表示モード");
        } else {
            // 🔥 シンプル問題表示：解答非表示、問題表示
            problemDiv.style.display = 'flex';
            answerDiv.style.display = 'none';
            
            console.log("📝 問題表示モード");
        }
        
        // 表示確認
        setTimeout(function() {
            if (showingAnswer) {
                const answerImg = answerDiv.querySelector('img');
                if (answerImg) checkSimpleImageVisibility(answerImg, currentIndex + 1, 'answer');
            } else {
                const problemImg = problemDiv.querySelector('img');
                if (problemImg) checkSimpleImageVisibility(problemImg, currentIndex + 1, 'problem');
            }
        }, 100);
    }
}

// ========== シンプルな画像表示確認 ==========
function checkSimpleImageVisibility(img, cardNumber, type) {
    const imageId = `card${cardNumber}_${type}`;
    const isVisible = img.offsetParent !== null && img.offsetWidth > 0 && img.offsetHeight > 0;
    const isLoaded = img.complete && img.naturalHeight !== 0;
    
    console.log(`🔍 シンプル画像確認: ${imageId}`);
    console.log(`  - 読み込み: ${isLoaded}, 表示: ${isVisible}`);
    console.log(`  - 表示サイズ: ${img.offsetWidth}x${img.offsetHeight}`);
    console.log(`  - 自然サイズ: ${img.naturalWidth}x${img.naturalHeight}`);
    
    // 表示すべき状態かチェック
    const shouldBeVisible = (type === 'problem' && !showingAnswer) || (type === 'answer' && showingAnswer);
    const currentCardIndex = cardNumber - 1;
    const isCurrentCard = currentCardIndex === currentIndex;
    
    if (isCurrentCard && shouldBeVisible && !isVisible) {
        console.warn(`⚠️ 表示すべき画像が非表示: ${imageId}`);
    } else if (isCurrentCard && !shouldBeVisible && isVisible) {
        console.warn(`⚠️ 非表示にすべき画像が表示: ${imageId}`);
    } else if (isCurrentCard) {
        console.log(`✅ 画像表示状態正常: ${imageId}`);
    }
    
    // 画像状況を更新
    if (imageLoadTracker.imageStatus[imageId]) {
        imageLoadTracker.imageStatus[imageId].visible = isVisible;
    }
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

// ========== シンプルなデバッグ機能 ==========
function debugStatus() {
    console.log("=== シンプルデバッグ情報 ===");
    console.log("カード数:", cards.length);
    console.log("現在のインデックス:", currentIndex);
    console.log("解答表示中:", showingAnswer);
    console.log("プリレンダリングカード数:", prerenderedCards.length);
    console.log("画像読み込み状況:", imageLoadTracker);
    
    // 現在のカードの状況
    if (prerenderedCards[currentIndex]) {
        const currentCard = prerenderedCards[currentIndex];
        const problemDiv = currentCard.querySelector('.problem-container');
        const answerDiv = currentCard.querySelector('.answer-container');
        
        console.log("=== 現在のカード状況 ===");
        console.log("カード表示:", currentCard.style.display);
        console.log("問題部分表示:", problemDiv ? problemDiv.style.display : "なし");
        console.log("解答部分表示:", answerDiv ? answerDiv.style.display : "なし");
        
        // 画像の状況
        const problemImg = problemDiv ? problemDiv.querySelector('img') : null;
        const answerImg = answerDiv ? answerDiv.querySelector('img') : null;
        
        if (problemImg) {
            console.log("問題画像:", {
                id: problemImg.id,
                visible: problemImg.offsetParent !== null,
                size: `${problemImg.offsetWidth}x${problemImg.offsetHeight}`,
                naturalSize: `${problemImg.naturalWidth}x${problemImg.naturalHeight}`
            });
        }
        
        if (answerImg) {
            console.log("解答画像:", {
                id: answerImg.id,
                visible: answerImg.offsetParent !== null,
                size: `${answerImg.offsetWidth}x${answerImg.offsetHeight}`,
                naturalSize: `${answerImg.naturalWidth}x${answerImg.naturalHeight}`
            });
        }
    }
}

// ========== シンプルな修復機能 ==========
function fixAllImages() {
    console.log("🛠️ シンプル画像修復実行");
    
    const currentCard = prerenderedCards[currentIndex];
    if (!currentCard) return;
    
    const problemDiv = currentCard.querySelector('.problem-container');
    const answerDiv = currentCard.querySelector('.answer-container');
    
    if (showingAnswer) {
        // 解答表示中：問題を非表示、解答を表示
        if (problemDiv) problemDiv.style.display = 'none';
        if (answerDiv) answerDiv.style.display = 'flex';
        console.log("🔧 解答表示状態に修復");
    } else {
        // 問題表示中：解答を非表示、問題を表示
        if (problemDiv) problemDiv.style.display = 'flex';
        if (answerDiv) answerDiv.style.display = 'none';
        console.log("🔧 問題表示状態に修復");
    }
    
    // 修復後の確認
    setTimeout(debugStatus, 300);
}

// ========== 初期化（シンプル版） ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔧 シンプルレイアウト版初期化開始");
    
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません");
        return;
    }
    
    cards = shuffle(rawCards.slice());
    currentIndex = 0;
    showingAnswer = false; // 必ず問題表示から開始
    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    
    console.log("📊 カードデータ: " + cards.length + "枚");
    console.log("📚 練習モード: " + isPracticeMode);
    console.log("🎯 初期表示状態: 問題表示");
    
    prerenderAllCards();
    setupInstantEvents();
    setupInstantKeyboard();
    
    // 初期化完了後の確認
    setTimeout(function() {
        console.log("📊 初期化完了後の状況:");
        debugStatus();
    }, 1000);
    
    console.log("🔧 シンプルレイアウト版初期化完了");
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
            case 'r':
                // デバッグ用：R キーで修復
                e.preventDefault();
                fixAllImages();
                break;
            case 'd':
                // デバッグ用：D キーでデバッグ情報
                e.preventDefault();
                debugStatus();
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
window.fixAllImages = fixAllImages;

console.log("🔧 シンプルレイアウト版読み込み完了");