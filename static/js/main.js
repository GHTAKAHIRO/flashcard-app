// キャッシュバスター
const CACHE_VERSION = Date.now();
console.log(`🔧 キャッシュ対策版 main.js v${CACHE_VERSION} が読み込まれました`);

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

// ========== 強制的な表示制御関数 ==========
function forceHideElement(element) {
    if (!element) return;
    
    // 複数の方法で確実に非表示にする
    element.style.setProperty('display', 'none', 'important');
    element.style.setProperty('visibility', 'hidden', 'important');
    element.style.setProperty('opacity', '0', 'important');
    element.style.setProperty('position', 'absolute', 'important');
    element.style.setProperty('left', '-9999px', 'important');
    element.style.setProperty('top', '-9999px', 'important');
    element.style.setProperty('width', '0', 'important');
    element.style.setProperty('height', '0', 'important');
    element.style.setProperty('overflow', 'hidden', 'important');
    element.setAttribute('aria-hidden', 'true');
    element.hidden = true;
}

function forceShowElement(element) {
    if (!element) return;
    
    // 複数の方法で確実に表示する
    element.style.removeProperty('display');
    element.style.removeProperty('visibility');
    element.style.removeProperty('opacity');
    element.style.removeProperty('position');
    element.style.removeProperty('left');
    element.style.removeProperty('top');
    element.style.removeProperty('width');
    element.style.removeProperty('height');
    element.style.removeProperty('overflow');
    element.removeAttribute('aria-hidden');
    element.hidden = false;
    
    // 表示設定
    element.style.setProperty('display', 'flex', 'important');
    element.style.setProperty('visibility', 'visible', 'important');
    element.style.setProperty('opacity', '1', 'important');
}

// ========== 確実な事前レンダリングシステム ==========
function prerenderAllCards() {
    console.log("🚀 確実な事前レンダリング開始");
    
    const flashcard = document.getElementById('flashcard');
    if (!flashcard) return;
    
    // フラッシュカードの基本設定
    flashcard.style.position = 'relative';
    flashcard.innerHTML = '';
    
    // 画像読み込み状況をリセット
    imageLoadTracker = { totalImages: 0, loadedImages: 0, failedImages: 0, imageStatus: {} };
    
    // 全カードを事前に作成
    cards.forEach(function(card, index) {
        const cardElement = createRobustCardElement(card, index);
        flashcard.appendChild(cardElement);
        prerenderedCards.push(cardElement);
        
        // 最初のカードのみ表示
        if (index === 0) {
            forceShowElement(cardElement);
            console.log(`🎯 カード1を強制表示に設定`);
        } else {
            forceHideElement(cardElement);
        }
    });
    
    console.log("✅ 確実な事前レンダリング完了: " + cards.length + "枚");
    
    // 初期化後に強制的に状態を確認・修正
    setTimeout(function() {
        forceCorrectInitialState();
    }, 100);
}

// ========== 堅牢なカード作成関数 ==========
function createRobustCardElement(card, index) {
    const container = document.createElement('div');
    container.className = 'prerendered-card';
    container.dataset.cardIndex = index;
    container.dataset.cardId = card.id;
    container.id = `card-${index + 1}`;
    
    const cardNumber = index + 1;
    
    // 問題部分
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-container';
    problemDiv.dataset.section = 'problem';
    problemDiv.dataset.cardNumber = cardNumber;
    problemDiv.id = `problem-${cardNumber}`;
    
    // 問題テキスト（画像の前に配置）
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = card.problem_number + ": " + card.topic;
        problemDiv.appendChild(text);
    }
    
    // 問題画像
    if (card.image_problem) {
        const img = createRobustImageElement(card.image_problem, '問題画像', cardNumber, 'problem');
        problemDiv.appendChild(img);
        imageLoadTracker.totalImages++;
    }
    
    // 解答部分（初期状態：確実に非表示）
    const answerDiv = document.createElement('div');
    answerDiv.className = 'answer-container';
    answerDiv.dataset.section = 'answer';
    answerDiv.dataset.cardNumber = cardNumber;
    answerDiv.id = `answer-${cardNumber}`;
    
    // 🔥 重要：解答部分を確実に非表示
    forceHideElement(answerDiv);
    
    // 解答画像
    if (card.image_answer) {
        const answerImg = createRobustImageElement(card.image_answer, '解答画像', cardNumber, 'answer');
        answerDiv.appendChild(answerImg);
        imageLoadTracker.totalImages++;
    }
    
    container.appendChild(problemDiv);
    container.appendChild(answerDiv);
    
    return container;
}

// ========== 堅牢な画像要素作成関数 ==========
function createRobustImageElement(src, alt, cardNumber, type) {
    const img = document.createElement('img');
    
    const imageId = `card${cardNumber}_${type}`;
    
    // 基本属性設定
    img.src = src + `?v=${CACHE_VERSION}`; // キャッシュバスター追加
    img.alt = alt;
    img.loading = 'eager';
    img.id = imageId;
    
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
        
        // 読み込み完了後に状態確認
        setTimeout(function() {
            checkAndFixImageVisibility(img, cardNumber, type);
        }, 50);
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

// ========== 初期状態強制修正関数 ==========
function forceCorrectInitialState() {
    console.log("🔧 初期状態を強制修正");
    
    // 全カードを確認して正しい状態に設定
    prerenderedCards.forEach(function(card, index) {
        const problemDiv = card.querySelector('.problem-container');
        const answerDiv = card.querySelector('.answer-container');
        
        if (index === 0) {
            // 最初のカード：問題表示、解答非表示
            if (problemDiv) forceShowElement(problemDiv);
            if (answerDiv) forceHideElement(answerDiv);
            console.log(`🎯 カード1: 問題表示、解答非表示に強制設定`);
        } else {
            // 他のカード：すべて非表示
            if (problemDiv) forceHideElement(problemDiv);
            if (answerDiv) forceHideElement(answerDiv);
            console.log(`👻 カード${index + 1}: 全体非表示に強制設定`);
        }
    });
    
    // グローバル状態を確実に設定
    currentIndex = 0;
    showingAnswer = false;
    
    console.log("✅ 初期状態強制修正完了");
}

// ========== 確実なカード切り替え ==========
function switchToCardInstantly(newIndex) {
    if (newIndex >= cards.length) return false;
    
    console.log(`🔄 確実なカード切り替え: ${currentIndex + 1} → ${newIndex + 1}`);
    
    // 全カードを一旦非表示にする
    prerenderedCards.forEach(function(card, index) {
        forceHideElement(card);
        
        const problemDiv = card.querySelector('.problem-container');
        const answerDiv = card.querySelector('.answer-container');
        if (problemDiv) forceHideElement(problemDiv);
        if (answerDiv) forceHideElement(answerDiv);
    });
    
    // 新しいカードのみ表示
    if (prerenderedCards[newIndex]) {
        const newCard = prerenderedCards[newIndex];
        forceShowElement(newCard);
        
        const problemDiv = newCard.querySelector('.problem-container');
        const answerDiv = newCard.querySelector('.answer-container');
        
        if (problemDiv && answerDiv) {
            // 問題を表示、解答を非表示
            forceShowElement(problemDiv);
            forceHideElement(answerDiv);
            
            console.log(`📝 カード${newIndex + 1}: 問題表示、解答完全非表示`);
        }
        
        console.log(`👁️ カード${newIndex + 1}を確実に表示`);
    }
    
    currentIndex = newIndex;
    showingAnswer = false; // フラグリセット
    
    updateProgressInstantly();
    
    // 切り替え後の状態確認
    setTimeout(function() {
        verifyCurrentState();
    }, 100);
    
    return true;
}

// ========== 確実な解答切り替え ==========
function toggleAnswerInstantly() {
    if (!prerenderedCards[currentIndex]) return;
    
    const currentCard = prerenderedCards[currentIndex];
    const problemDiv = currentCard.querySelector('.problem-container');
    const answerDiv = currentCard.querySelector('.answer-container');
    
    if (problemDiv && answerDiv) {
        showingAnswer = !showingAnswer;
        
        console.log(`🔄 確実な解答切り替え: ${showingAnswer ? '問題→解答' : '解答→問題'} (カード${currentIndex + 1})`);
        
        if (showingAnswer) {
            // 🔥 解答表示：問題を完全非表示、解答を表示
            forceHideElement(problemDiv);
            forceShowElement(answerDiv);
            
            console.log("👁️ 解答表示モード：問題完全非表示");
        } else {
            // 🔥 問題表示：解答を完全非表示、問題を表示
            forceHideElement(answerDiv);
            forceShowElement(problemDiv);
            
            console.log("📝 問題表示モード：解答完全非表示");
        }
        
        // 切り替え後の状態確認
        setTimeout(function() {
            verifyCurrentState();
        }, 100);
    }
}

// ========== 状態確認・修正関数 ==========
function checkAndFixImageVisibility(img, cardNumber, type) {
    const imageId = `card${cardNumber}_${type}`;
    const isVisible = img.offsetParent !== null && img.offsetWidth > 0 && img.offsetHeight > 0;
    const isLoaded = img.complete && img.naturalHeight !== 0;
    
    console.log(`🔍 画像確認: ${imageId}`);
    console.log(`  - 読み込み: ${isLoaded}, 表示: ${isVisible}`);
    console.log(`  - 表示サイズ: ${img.offsetWidth}x${img.offsetHeight}`);
    console.log(`  - 自然サイズ: ${img.naturalWidth}x${img.naturalHeight}`);
    
    // 表示すべき状態かチェック
    const shouldBeVisible = (type === 'problem' && !showingAnswer) || (type === 'answer' && showingAnswer);
    const currentCardIndex = cardNumber - 1;
    const isCurrentCard = currentCardIndex === currentIndex;
    
    if (isCurrentCard && shouldBeVisible && !isVisible) {
        console.warn(`⚠️ 表示すべき画像が非表示: ${imageId} - 修正します`);
        const container = img.closest('.problem-container, .answer-container');
        if (container) forceShowElement(container);
    } else if (isCurrentCard && !shouldBeVisible && isVisible) {
        console.warn(`⚠️ 非表示にすべき画像が表示: ${imageId} - 修正します`);
        const container = img.closest('.problem-container, .answer-container');
        if (container) forceHideElement(container);
    } else if (isCurrentCard) {
        console.log(`✅ 画像表示状態正常: ${imageId}`);
    }
    
    // 画像状況を更新
    if (imageLoadTracker.imageStatus[imageId]) {
        imageLoadTracker.imageStatus[imageId].visible = isVisible;
    }
}

// ========== 現在状態の検証関数 ==========
function verifyCurrentState() {
    console.log("🔍 現在状態を検証中...");
    
    if (!prerenderedCards[currentIndex]) return;
    
    const currentCard = prerenderedCards[currentIndex];
    const problemDiv = currentCard.querySelector('.problem-container');
    const answerDiv = currentCard.querySelector('.answer-container');
    
    const problemVisible = problemDiv ? (problemDiv.offsetParent !== null) : false;
    const answerVisible = answerDiv ? (answerDiv.offsetParent !== null) : false;
    
    console.log(`📊 カード${currentIndex + 1}状態: 問題=${problemVisible}, 解答=${answerVisible}, フラグ=${showingAnswer}`);
    
    // 状態が正しくない場合は修正
    if (showingAnswer && problemVisible) {
        console.warn("⚠️ 解答表示中なのに問題が見えています - 修正します");
        if (problemDiv) forceHideElement(problemDiv);
    }
    
    if (showingAnswer && !answerVisible) {
        console.warn("⚠️ 解答表示中なのに解答が見えません - 修正します");
        if (answerDiv) forceShowElement(answerDiv);
    }
    
    if (!showingAnswer && answerVisible) {
        console.warn("⚠️ 問題表示中なのに解答が見えています - 修正します");
        if (answerDiv) forceHideElement(answerDiv);
    }
    
    if (!showingAnswer && !problemVisible) {
        console.warn("⚠️ 問題表示中なのに問題が見えません - 修正します");
        if (problemDiv) forceShowElement(problemDiv);
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

// ========== 確実なデバッグ機能 ==========
function debugStatus() {
    console.log("=== 確実なデバッグ情報 ===");
    console.log("カード数:", cards.length);
    console.log("現在のインデックス:", currentIndex);
    console.log("解答表示中:", showingAnswer);
    console.log("プリレンダリングカード数:", prerenderedCards.length);
    console.log("画像読み込み状況:", imageLoadTracker);
    
    // 全カードの状況
    console.log("=== 全カード状況 ===");
    prerenderedCards.forEach(function(card, index) {
        const problemDiv = card.querySelector('.problem-container');
        const answerDiv = card.querySelector('.answer-container');
        
        const cardVisible = card.offsetParent !== null;
        const problemVisible = problemDiv ? problemDiv.offsetParent !== null : false;
        const answerVisible = answerDiv ? answerDiv.offsetParent !== null : false;
        
        console.log(`カード${index + 1}: カード=${cardVisible}, 問題=${problemVisible}, 解答=${answerVisible}`);
    });
    
    // 現在のカードの詳細
    if (prerenderedCards[currentIndex]) {
        const currentCard = prerenderedCards[currentIndex];
        const problemDiv = currentCard.querySelector('.problem-container');
        const answerDiv = currentCard.querySelector('.answer-container');
        
        console.log("=== 現在のカード詳細 ===");
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

// ========== 確実な修復機能 ==========
function fixAllImages() {
    console.log("🛠️ 確実な修復実行");
    
    // 全カードを一旦リセット
    prerenderedCards.forEach(function(card, index) {
        const problemDiv = card.querySelector('.problem-container');
        const answerDiv = card.querySelector('.answer-container');
        
        if (index === currentIndex) {
            // 現在のカード
            forceShowElement(card);
            
            if (showingAnswer) {
                forceHideElement(problemDiv);
                forceShowElement(answerDiv);
                console.log(`🔧 カード${index + 1}: 解答表示状態に修復`);
            } else {
                forceShowElement(problemDiv);
                forceHideElement(answerDiv);
                console.log(`🔧 カード${index + 1}: 問題表示状態に修復`);
            }
        } else {
            // 他のカード
            forceHideElement(card);
            forceHideElement(problemDiv);
            forceHideElement(answerDiv);
            console.log(`🔧 カード${index + 1}: 完全非表示に修復`);
        }
    });
    
    // 修復後の確認
    setTimeout(function() {
        verifyCurrentState();
        debugStatus();
    }, 200);
}

// ========== 初期化（確実版） ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔧 キャッシュ対策版初期化開始");
    
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
    
    // 段階的な初期化確認
    setTimeout(function() {
        console.log("📊 初期化1秒後の状況:");
        verifyCurrentState();
    }, 1000);
    
    setTimeout(function() {
        console.log("📊 初期化2秒後の状況:");
        debugStatus();
    }, 2000);
    
    console.log("🔧 キャッシュ対策版初期化完了");
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
            case 'v':
                // デバッグ用：V キーで状態検証
                e.preventDefault();
                verifyCurrentState();
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

window.markUnknown = function() {
    handleAnswerInstantly('unknown');
};

// デバッグ用グローバル関数
window.debugStatus = debugStatus;
window.fixAllImages = fixAllImages;
window.verifyCurrentState = verifyCurrentState;
window.forceCorrectInitialState = forceCorrectInitialState;

console.log(`🔧 キャッシュ対策版読み込み完了 v${CACHE_VERSION}`);