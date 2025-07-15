if (window.location.pathname.startsWith('/admin')) {
  // admin画面ではmain.jsの処理をスキップ（フラッシュカード機能は不要）
  console.log('main.js: 管理画面のため、フラッシュカード機能をスキップします');
} else {
// ここから下に従来のmain.jsの処理が続く

console.log("🔧 アニメーション対応版 main.js が読み込まれました");

// ========== CSRFトークン取得 ==========
const csrfToken = window.csrfToken || '';

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
    imageStatus: {}
};

// ========== アニメーション用変数 ==========
let isAnimating = false;
let completionAnimationActive = false;

// ========== 完了時アニメーション作成 ==========
function createCompletionAnimation() {
    const overlay = document.createElement('div');
    overlay.id = 'completion-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: linear-gradient(135deg, #28a745, #20c997, #17a2b8);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        opacity: 0;
        transform: scale(0.8);
        transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        backdrop-filter: blur(10px);
    `;
    
    const content = document.createElement('div');
    content.style.cssText = `
        text-align: center;
        color: white;
        transform: translateY(20px);
        opacity: 0;
        transition: all 0.6s ease 0.2s;
    `;
    
    const icon = document.createElement('div');
    icon.innerHTML = '🎉';
    icon.style.cssText = `
        font-size: 4rem;
        margin-bottom: 1rem;
        animation: bounce 0.6s ease infinite alternate;
    `;
    
    const title = document.createElement('h2');
    title.textContent = '完了しました！';
    title.style.cssText = `
        font-size: 2.5rem;
        margin: 0 0 1rem 0;
        font-weight: bold;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    `;
    
    const subtitle = document.createElement('p');
    subtitle.textContent = '次の画面に移動しています...';
    subtitle.style.cssText = `
        font-size: 1.2rem;
        margin: 0;
        opacity: 0.9;
    `;
    
    const spinner = document.createElement('div');
    spinner.style.cssText = `
        width: 40px;
        height: 40px;
        border: 4px solid rgba(255,255,255,0.3);
        border-top: 4px solid white;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-top: 1.5rem;
    `;
    
    content.appendChild(icon);
    content.appendChild(title);
    content.appendChild(subtitle);
    content.appendChild(spinner);
    overlay.appendChild(content);
    
    // CSS animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes bounce {
            0% { transform: translateY(0); }
            100% { transform: translateY(-10px); }
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        @keyframes fadeOut {
            0% { opacity: 1; transform: scale(1); }
            100% { opacity: 0; transform: scale(1.1); }
        }
    `;
    document.head.appendChild(style);
    
    document.body.appendChild(overlay);
    
    // アニメーション開始
    requestAnimationFrame(() => {
        overlay.style.opacity = '1';
        overlay.style.transform = 'scale(1)';
        
        setTimeout(() => {
            content.style.opacity = '1';
            content.style.transform = 'translateY(0)';
        }, 200);
    });
    
    return overlay;
}

// ========== ページ遷移アニメーション ==========
function createPageTransition() {
    const transition = document.createElement('div');
    transition.id = 'page-transition';
    transition.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: linear-gradient(45deg, #007bff, #0056b3);
        z-index: 9998;
        opacity: 0;
        transform: translateX(-100%);
        transition: all 0.3s ease-in-out;
    `;
    
    document.body.appendChild(transition);
    
    requestAnimationFrame(() => {
        transition.style.opacity = '1';
        transition.style.transform = 'translateX(0)';
    });
    
    return transition;
}

// ========== 核爆弾級の非表示関数 ==========
function nuclearHide(element) {
    if (!element) return;
    
    console.log(`💥 核爆弾級非表示: ${element.id || element.className}`);
    
    element.style.setProperty('display', 'none', 'important');
    element.style.setProperty('visibility', 'hidden', 'important');
    element.style.setProperty('opacity', '0', 'important');
    element.style.setProperty('position', 'absolute', 'important');
    element.style.setProperty('left', '-99999px', 'important');
    element.style.setProperty('top', '-99999px', 'important');
    element.style.setProperty('width', '0px', 'important');
    element.style.setProperty('height', '0px', 'important');
    element.style.setProperty('max-width', '0px', 'important');
    element.style.setProperty('max-height', '0px', 'important');
    element.style.setProperty('overflow', 'hidden', 'important');
    element.style.setProperty('clip', 'rect(0,0,0,0)', 'important');
    element.style.setProperty('transform', 'scale(0)', 'important');
    element.style.setProperty('z-index', '-9999', 'important');
    
    element.setAttribute('aria-hidden', 'true');
    element.setAttribute('hidden', 'true');
    element.hidden = true;
    
    const images = element.querySelectorAll('img');
    images.forEach(img => {
        img.style.setProperty('display', 'none', 'important');
        img.style.setProperty('visibility', 'hidden', 'important');
        img.style.setProperty('opacity', '0', 'important');
        img.style.setProperty('position', 'absolute', 'important');
        img.style.setProperty('left', '-99999px', 'important');
        img.style.setProperty('top', '-99999px', 'important');
        img.style.setProperty('width', '0px', 'important');
        img.style.setProperty('height', '0px', 'important');
    });
}

function nuclearShow(element) {
    if (!element) return;
    
    console.log(`✨ 核爆弾級表示: ${element.id || element.className}`);
    
    const propertiesToRemove = [
        'display', 'visibility', 'opacity', 'position', 'left', 'top',
        'width', 'height', 'max-width', 'max-height', 'overflow',
        'clip', 'transform', 'z-index'
    ];
    
    propertiesToRemove.forEach(prop => {
        element.style.removeProperty(prop);
    });
    
    element.style.setProperty('display', 'flex', 'important');
    element.style.setProperty('visibility', 'visible', 'important');
    element.style.setProperty('opacity', '1', 'important');
    
    element.removeAttribute('aria-hidden');
    element.removeAttribute('hidden');
    element.hidden = false;
    
    const images = element.querySelectorAll('img');
    images.forEach(img => {
        const imagePropertiesToRemove = [
            'display', 'visibility', 'opacity', 'position', 'left', 'top',
            'width', 'height'
        ];
        
        imagePropertiesToRemove.forEach(prop => {
            img.style.removeProperty(prop);
        });
        
        img.style.setProperty('display', 'block', 'important');
        img.style.setProperty('visibility', 'visible', 'important');
        img.style.setProperty('opacity', '1', 'important');
    });
}

// ========== 超堅牢カード作成 ==========
function createUltraRobustCard(card, index) {
    const container = document.createElement('div');
    container.className = 'prerendered-card ultra-robust-card';
    container.dataset.cardIndex = index;
    container.dataset.cardId = card.id;
    container.id = `ultra-card-${index + 1}`;
    
    const cardNumber = index + 1;
    
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-container ultra-problem';
    problemDiv.id = `ultra-problem-${cardNumber}`;
    problemDiv.dataset.section = 'problem';
    
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = card.problem_number + ": " + card.topic;
        text.className = 'ultra-text';
        problemDiv.appendChild(text);
    }
    
    if (card.image_problem) {
        const img = createUltraRobustImage(card.image_problem, '問題画像', cardNumber, 'problem');
        problemDiv.appendChild(img);
        imageLoadTracker.totalImages++;
    }
    
    const answerDiv = document.createElement('div');
    answerDiv.className = 'answer-container ultra-answer';
    answerDiv.id = `ultra-answer-${cardNumber}`;
    answerDiv.dataset.section = 'answer';
    
    if (card.image_answer) {
        const answerImg = createUltraRobustImage(card.image_answer, '解答画像', cardNumber, 'answer');
        answerDiv.appendChild(answerImg);
        imageLoadTracker.totalImages++;
    }
    
    container.appendChild(problemDiv);
    container.appendChild(answerDiv);
    
    return container;
}

function createUltraRobustImage(src, alt, cardNumber, type) {
    const img = document.createElement('img');
    
    const imageId = `ultra-card${cardNumber}-${type}`;
    
    img.src = src;
    img.alt = alt;
    img.loading = 'eager';
    img.id = imageId;
    img.className = `ultra-image ultra-${type}`;
    
    img.dataset.cardNumber = cardNumber;
    img.dataset.imageType = type;
    img.dataset.originalSrc = src;
    
    imageLoadTracker.imageStatus[imageId] = {
        cardNumber: cardNumber,
        type: type,
        src: src,
        loaded: false,
        failed: false,
        visible: false
    };
    
    img.onload = function() {
        imageLoadTracker.loadedImages++;
        imageLoadTracker.imageStatus[imageId].loaded = true;
        
        console.log(`✅ 超堅牢画像読み込み: ${imageId} (${imageLoadTracker.loadedImages}/${imageLoadTracker.totalImages})`);
        
        setTimeout(() => ultraVerifyImageState(img, cardNumber, type), 50);
    };
    
    img.onerror = function() {
        imageLoadTracker.failedImages++;
        imageLoadTracker.imageStatus[imageId].failed = true;
        
        console.error(`❌ 超堅牢画像失敗: ${imageId}`);
    };
    
    return img;
}

// ========== 事前レンダリング ==========
function prerenderAllCards() {
    console.log("🚀 アニメーション対応事前レンダリング開始");
    
    const flashcard = document.getElementById('flashcard');
    if (!flashcard) return;
    
    flashcard.innerHTML = '';
    imageLoadTracker = { totalImages: 0, loadedImages: 0, failedImages: 0, imageStatus: {} };
    prerenderedCards = [];
    
    cards.forEach(function(card, index) {
        const cardElement = createUltraRobustCard(card, index);
        flashcard.appendChild(cardElement);
        prerenderedCards.push(cardElement);
    });
    
    console.log("✅ アニメーション対応事前レンダリング完了: " + cards.length + "枚");
    
    setTimeout(() => ultraForceInitialState(), 100);
}

function ultraForceInitialState() {
    console.log("💪 超強力初期状態設定開始");
    
    prerenderedCards.forEach((card, index) => {
        nuclearHide(card);
        
        const problemDiv = card.querySelector('.problem-container');
        const answerDiv = card.querySelector('.answer-container');
        
        nuclearHide(problemDiv);
        nuclearHide(answerDiv);
    });
    
    if (prerenderedCards[0]) {
        const firstCard = prerenderedCards[0];
        const problemDiv = firstCard.querySelector('.problem-container');
        const answerDiv = firstCard.querySelector('.answer-container');
        
        nuclearShow(firstCard);
        nuclearShow(problemDiv);
        nuclearHide(answerDiv);
        
        console.log("🎯 最初のカードを超強力表示");
    }
    
    currentIndex = 0;
    showingAnswer = false;
    
    console.log("✅ 超強力初期状態設定完了");
    setTimeout(() => ultraVerifyAllStates(), 200);
}

// ========== カード切り替え（アニメーション対応） ==========
function switchToCardInstantly(newIndex) {
    if (newIndex >= cards.length) return false;
    if (isAnimating) return false;
    
    console.log(`🔄 アニメーション対応カード切り替え: ${currentIndex + 1} → ${newIndex + 1}`);
    
    prerenderedCards.forEach((card, index) => {
        nuclearHide(card);
        const problemDiv = card.querySelector('.problem-container');
        const answerDiv = card.querySelector('.answer-container');
        nuclearHide(problemDiv);
        nuclearHide(answerDiv);
    });
    
    if (prerenderedCards[newIndex]) {
        const newCard = prerenderedCards[newIndex];
        const problemDiv = newCard.querySelector('.problem-container');
        const answerDiv = newCard.querySelector('.answer-container');
        
        nuclearShow(newCard);
        nuclearShow(problemDiv);
        nuclearHide(answerDiv);
        
        console.log(`📝 カード${newIndex + 1}: 問題表示、解答核爆弾級非表示`);
    }
    
    currentIndex = newIndex;
    showingAnswer = false;
    
    updateProgressInstantly();
    setTimeout(() => ultraVerifyAllStates(), 100);
    
    return true;
}

// ========== 解答切り替え ==========
function toggleAnswerInstantly() {
    if (!prerenderedCards[currentIndex] || isAnimating) return;
    
    const currentCard = prerenderedCards[currentIndex];
    const problemDiv = currentCard.querySelector('.problem-container');
    const answerDiv = currentCard.querySelector('.answer-container');
    
    if (problemDiv && answerDiv) {
        showingAnswer = !showingAnswer;
        
        console.log(`🔄 確実な解答切り替え: ${showingAnswer ? '問題→解答' : '解答→問題'}`);
        
        if (showingAnswer) {
            nuclearHide(problemDiv);
            nuclearShow(answerDiv);
            console.log("👁️ 解答表示：問題核爆弾級非表示");
        } else {
            nuclearHide(answerDiv);
            nuclearShow(problemDiv);
            console.log("📝 問題表示：解答核爆弾級非表示");
        }
        
        setTimeout(() => ultraVerifyAllStates(), 100);
    }
}

// ========== 状態検証・修正関数 ==========
function ultraVerifyImageState(img, cardNumber, type) {
    const imageId = img.id;
    const isVisible = img.offsetParent !== null && img.offsetWidth > 0 && img.offsetHeight > 0;
    
    console.log(`🔍 超検証 ${imageId}: 表示=${isVisible}`);
    
    const shouldBeVisible = (type === 'problem' && !showingAnswer) || (type === 'answer' && showingAnswer);
    const isCurrentCard = (cardNumber - 1) === currentIndex;
    
    if (isCurrentCard && shouldBeVisible && !isVisible) {
        console.warn(`⚠️ 表示すべき画像が非表示: ${imageId} → 修正中`);
        const container = img.closest('.problem-container, .answer-container');
        if (container) nuclearShow(container);
    } else if (isCurrentCard && !shouldBeVisible && isVisible) {
        console.warn(`⚠️ 非表示にすべき画像が表示: ${imageId} → 核爆弾級非表示`);
        const container = img.closest('.problem-container, .answer-container');
        if (container) nuclearHide(container);
    }
}

function ultraVerifyAllStates() {
    console.log("🔍 全状態超検証開始");
    
    prerenderedCards.forEach((card, index) => {
        const problemDiv = card.querySelector('.problem-container');
        const answerDiv = card.querySelector('.answer-container');
        
        const cardVisible = card.offsetParent !== null;
        const problemVisible = problemDiv ? problemDiv.offsetParent !== null : false;
        const answerVisible = answerDiv ? answerDiv.offsetParent !== null : false;
        
        console.log(`📊 カード${index + 1}: カード=${cardVisible}, 問題=${problemVisible}, 解答=${answerVisible}`);
        
        if (index === currentIndex) {
            if (!cardVisible) {
                console.warn(`⚠️ 現在カードが非表示 → 修正`);
                nuclearShow(card);
            }
            
            if (showingAnswer) {
                if (problemVisible) {
                    console.warn(`⚠️ 解答モードで問題表示 → 核爆弾級非表示`);
                    nuclearHide(problemDiv);
                }
                if (!answerVisible) {
                    console.warn(`⚠️ 解答モードで解答非表示 → 表示`);
                    nuclearShow(answerDiv);
                }
            } else {
                if (answerVisible) {
                    console.warn(`⚠️ 問題モードで解答表示 → 核爆弾級非表示`);
                    nuclearHide(answerDiv);
                }
                if (!problemVisible) {
                    console.warn(`⚠️ 問題モードで問題非表示 → 表示`);
                    nuclearShow(problemDiv);
                }
            }
        } else {
            if (cardVisible || problemVisible || answerVisible) {
                console.warn(`⚠️ 非現在カードが表示 → 核爆弾級非表示`);
                nuclearHide(card);
                nuclearHide(problemDiv);
                nuclearHide(answerDiv);
            }
        }
    });
    
    console.log("✅ 全状態超検証完了");
}

function updateProgressInstantly() {
    const progressElement = document.getElementById('progress-info');
    if (progressElement) {
        progressElement.innerHTML = '<i class="fas fa-chart-line"></i> ' + (currentIndex + 1) + ' / ' + cards.length;
    }
}

// ========== 瞬間回答処理（アニメーション対応） ==========
function handleAnswerInstantly(result) {
    if (isAnimating || completionAnimationActive) return;
    
    console.log("⚡ 瞬間回答: " + result + " (カード" + (currentIndex + 1) + "/" + cards.length + ")");
    
    const currentCardId = cards[currentIndex].id;
    
    updateCountersInstantly(result);
    triggerButtonFeedback(result);
    
    const success = switchToCardInstantly(currentIndex + 1);
    
    if (!success) {
        console.log("🏁 全カード完了 - アニメーション開始");
        completionAnimationActive = true;
        isAnimating = true;
        
        // 完了アニメーション表示
        const overlay = createCompletionAnimation();
        
        // 最後のカードのログを送信
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
    const data = {
        word_id: cardId,
        is_correct: (result === 'known'),
        chunk_id: window.currentChunk || 1
    };
    console.log("送信データ (sendResultBackground):", data);
    fetch('/log_result', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        credentials: 'include',
        body: JSON.stringify(data)
    }).catch(function(error) {
        console.error('非同期ログエラー:', error);
    });
}

// ========== 完了処理（高速化・アニメーション対応） ==========
function handleCardCompletionSync(cardId, result) {
    const data = {
        word_id: cardId,
        is_correct: (result === 'known'),
        chunk_id: window.currentChunk || 1
    };
    console.log("送信データ (handleCardCompletionSync):", data);
    fetch('/log_result', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        credentials: 'include',
        body: JSON.stringify(data)
    }).then(function(response) {
        return response.json();
    }).then(function(data) {
        console.log("✅ 完了時サーバーレスポンス:", data);
        
        // ページ遷移アニメーション開始
        const transition = createPageTransition();
        
        // 短い待機時間で遷移（高速化）
        setTimeout(function() {
            window.location.href = '/prepare/' + getCurrentSource();
        }, 500); // 1000ms → 500ms に高速化
        
    }).catch(function(error) {
        console.error('❌ 完了時ログエラー:', error);
        
        // エラー時も高速遷移
        setTimeout(function() {
            window.location.href = '/prepare/' + getCurrentSource();
        }, 300); // エラー時はさらに高速
    });
}

// ========== デバッグ機能 ==========
function debugStatus() {
    console.log("=== アニメーション対応デバッグ情報 ===");
    console.log("カード数:", cards.length);
    console.log("現在のインデックス:", currentIndex);
    console.log("解答表示中:", showingAnswer);
    console.log("アニメーション中:", isAnimating);
    console.log("完了アニメーション中:", completionAnimationActive);
    console.log("画像読み込み状況:", imageLoadTracker);
    
    ultraVerifyAllStates();
}

function fixAllImages() {
    console.log("🛠️ 完全修復実行");
    ultraVerifyAllStates();
}

// ========== 初期化（アニメーション対応） ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔧 アニメーション対応版初期化開始");
    
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません");
        return;
    }
    
    cards = shuffle(rawCards.slice());
    currentIndex = 0;
    showingAnswer = false;
    isAnimating = false;
    completionAnimationActive = false;
    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'practice');
    
    console.log("📊 カードデータ: " + cards.length + "枚");
    console.log("🎯 初期表示状態: 問題表示");
    
    prerenderAllCards();
    setupInstantEvents();
    setupInstantKeyboard();
    
    setTimeout(() => {
        console.log("📊 1秒後の状況:");
        ultraVerifyAllStates();
    }, 1000);
    
    setTimeout(() => {
        console.log("📊 3秒後の状況:");
        debugStatus();
    }, 3000);
    
    console.log("🔧 アニメーション対応版初期化完了");
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
        if (isAnimating || completionAnimationActive) return;
        
        switch(e.key.toLowerCase()) {
            case 'f':
            case 'arrowleft':
                e.preventDefault();
                handleAnswerInstantly('known');
                break;
            case 'j':
            case 'arrowright':
                e.preventDefault();
                handleAnswerInstantly('unknown');
                break;
            case ' ':
                e.preventDefault();
                toggleAnswerInstantly();
                break;
            case 'r':
                e.preventDefault();
                fixAllImages();
                break;
            case 'd':
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

// ========== グローバル関数 ==========
window.toggleAnswer = function() {
    toggleAnswerInstantly();
};

window.markKnown = function() {
    handleAnswerInstantly('known');
};

window.markUnknown = function() {
    handleAnswerInstantly('unknown');
};

window.debugStatus = debugStatus;
window.fixAllImages = fixAllImages;
window.ultraVerifyAllStates = ultraVerifyAllStates;

console.log("🔧 アニメーション対応版読み込み完了");
}