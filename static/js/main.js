console.log("🔧 完全修正版 main.js が読み込まれました");

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

// ========== 核爆弾級の非表示関数 ==========
function nuclearHide(element) {
    if (!element) return;
    
    console.log(`💥 核爆弾級非表示: ${element.id || element.className}`);
    
    // すべての可能な非表示方法を使用
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
    
    // DOM属性も設定
    element.setAttribute('aria-hidden', 'true');
    element.setAttribute('hidden', 'true');
    element.hidden = true;
    
    // 子要素の画像も強制非表示
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

// ========== 核爆弾級の表示関数 ==========
function nuclearShow(element) {
    if (!element) return;
    
    console.log(`✨ 核爆弾級表示: ${element.id || element.className}`);
    
    // すべての非表示スタイルをクリア
    const propertiesToRemove = [
        'display', 'visibility', 'opacity', 'position', 'left', 'top',
        'width', 'height', 'max-width', 'max-height', 'overflow',
        'clip', 'transform', 'z-index'
    ];
    
    propertiesToRemove.forEach(prop => {
        element.style.removeProperty(prop);
    });
    
    // 確実な表示設定
    element.style.setProperty('display', 'flex', 'important');
    element.style.setProperty('visibility', 'visible', 'important');
    element.style.setProperty('opacity', '1', 'important');
    
    // DOM属性をクリア
    element.removeAttribute('aria-hidden');
    element.removeAttribute('hidden');
    element.hidden = false;
    
    // 子要素の画像も表示
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

// ========== 完全DOM削除・再作成システム ==========
function nukeAndRebuildCard(cardIndex) {
    console.log(`🚀 カード${cardIndex + 1}を完全再構築`);
    
    const flashcard = document.getElementById('flashcard');
    if (!flashcard || !cards[cardIndex]) return;
    
    // 既存のカードを完全削除
    if (prerenderedCards[cardIndex]) {
        prerenderedCards[cardIndex].remove();
    }
    
    // 新しいカードを作成
    const newCard = createUltraRobustCard(cards[cardIndex], cardIndex);
    
    // 適切な位置に挿入
    if (cardIndex === 0) {
        flashcard.insertBefore(newCard, flashcard.firstChild);
    } else {
        const previousCard = prerenderedCards[cardIndex - 1];
        if (previousCard && previousCard.nextSibling) {
            flashcard.insertBefore(newCard, previousCard.nextSibling);
        } else {
            flashcard.appendChild(newCard);
        }
    }
    
    // 配列を更新
    prerenderedCards[cardIndex] = newCard;
    
    // 表示状態を設定
    if (cardIndex === currentIndex) {
        nuclearShow(newCard);
        
        const problemDiv = newCard.querySelector('.problem-container');
        const answerDiv = newCard.querySelector('.answer-container');
        
        if (showingAnswer) {
            nuclearHide(problemDiv);
            nuclearShow(answerDiv);
        } else {
            nuclearShow(problemDiv);
            nuclearHide(answerDiv);
        }
    } else {
        nuclearHide(newCard);
    }
    
    console.log(`✅ カード${cardIndex + 1}再構築完了`);
}

// ========== 超堅牢カード作成 ==========
function createUltraRobustCard(card, index) {
    const container = document.createElement('div');
    container.className = 'prerendered-card ultra-robust-card';
    container.dataset.cardIndex = index;
    container.dataset.cardId = card.id;
    container.id = `ultra-card-${index + 1}`;
    
    const cardNumber = index + 1;
    
    // 問題部分
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-container ultra-problem';
    problemDiv.id = `ultra-problem-${cardNumber}`;
    problemDiv.dataset.section = 'problem';
    
    // 問題テキスト
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = card.problem_number + ": " + card.topic;
        text.className = 'ultra-text';
        problemDiv.appendChild(text);
    }
    
    // 問題画像
    if (card.image_problem) {
        const img = createUltraRobustImage(card.image_problem, '問題画像', cardNumber, 'problem');
        problemDiv.appendChild(img);
        imageLoadTracker.totalImages++;
    }
    
    // 解答部分
    const answerDiv = document.createElement('div');
    answerDiv.className = 'answer-container ultra-answer';
    answerDiv.id = `ultra-answer-${cardNumber}`;
    answerDiv.dataset.section = 'answer';
    
    // 解答画像
    if (card.image_answer) {
        const answerImg = createUltraRobustImage(card.image_answer, '解答画像', cardNumber, 'answer');
        answerDiv.appendChild(answerImg);
        imageLoadTracker.totalImages++;
    }
    
    container.appendChild(problemDiv);
    container.appendChild(answerDiv);
    
    return container;
}

// ========== 超堅牢画像作成 ==========
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
    
    // 画像状況を初期化
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
        
        // 読み込み後の即座チェック
        setTimeout(() => ultraVerifyImageState(img, cardNumber, type), 50);
    };
    
    img.onerror = function() {
        imageLoadTracker.failedImages++;
        imageLoadTracker.imageStatus[imageId].failed = true;
        
        console.error(`❌ 超堅牢画像失敗: ${imageId}`);
    };
    
    return img;
}

// ========== 事前レンダリング（完全版） ==========
function prerenderAllCards() {
    console.log("🚀 完全事前レンダリング開始");
    
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
    
    console.log("✅ 完全事前レンダリング完了: " + cards.length + "枚");
    
    // 初期状態を強制設定
    setTimeout(() => ultraForceInitialState(), 100);
}

// ========== 超強力初期状態設定 ==========
function ultraForceInitialState() {
    console.log("💪 超強力初期状態設定開始");
    
    // すべてのカードを一旦核爆弾級非表示
    prerenderedCards.forEach((card, index) => {
        nuclearHide(card);
        
        const problemDiv = card.querySelector('.problem-container');
        const answerDiv = card.querySelector('.answer-container');
        
        nuclearHide(problemDiv);
        nuclearHide(answerDiv);
    });
    
    // 最初のカードのみ表示
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
    
    // 検証
    setTimeout(() => ultraVerifyAllStates(), 200);
}

// ========== カード切り替え（完全版） ==========
function switchToCardInstantly(newIndex) {
    if (newIndex >= cards.length) return false;
    
    console.log(`🔄 完全カード切り替え: ${currentIndex + 1} → ${newIndex + 1}`);
    
    // 全カードを核爆弾級非表示
    prerenderedCards.forEach((card, index) => {
        nuclearHide(card);
        const problemDiv = card.querySelector('.problem-container');
        const answerDiv = card.querySelector('.answer-container');
        nuclearHide(problemDiv);
        nuclearHide(answerDiv);
    });
    
    // 新しいカードのみ表示
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
    
    // 切り替え後検証
    setTimeout(() => ultraVerifyAllStates(), 100);
    
    return true;
}

// ========== 解答切り替え（完全版） ==========
function toggleAnswerInstantly() {
    if (!prerenderedCards[currentIndex]) return;
    
    const currentCard = prerenderedCards[currentIndex];
    const problemDiv = currentCard.querySelector('.problem-container');
    const answerDiv = currentCard.querySelector('.answer-container');
    
    if (problemDiv && answerDiv) {
        showingAnswer = !showingAnswer;
        
        console.log(`🔄 完全解答切り替え: ${showingAnswer ? '問題→解答' : '解答→問題'}`);
        
        if (showingAnswer) {
            nuclearHide(problemDiv);
            nuclearShow(answerDiv);
            console.log("👁️ 解答表示：問題核爆弾級非表示");
        } else {
            nuclearHide(answerDiv);
            nuclearShow(problemDiv);
            console.log("📝 問題表示：解答核爆弾級非表示");
        }
        
        // 切り替え後検証
        setTimeout(() => ultraVerifyAllStates(), 100);
    }
}

// ========== 超強力状態検証 ==========
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
            // 現在のカード
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
            // 他のカード
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

// ========== デバッグ機能 ==========
function debugStatus() {
    console.log("=== 完全デバッグ情報 ===");
    console.log("カード数:", cards.length);
    console.log("現在のインデックス:", currentIndex);
    console.log("解答表示中:", showingAnswer);
    console.log("画像読み込み状況:", imageLoadTracker);
    
    ultraVerifyAllStates();
}

function fixAllImages() {
    console.log("🛠️ 完全修復実行");
    ultraVerifyAllStates();
}

// ========== 核爆弾級完全修復 ==========
function nuclearReset() {
    console.log("💥 核爆弾級完全修復開始");
    
    // 全カードを削除して再作成
    cards.forEach((card, index) => {
        nukeAndRebuildCard(index);
    });
    
    // 初期状態を再設定
    setTimeout(() => {
        ultraForceInitialState();
    }, 200);
    
    console.log("✅ 核爆弾級完全修復完了");
}

// ========== 初期化（完全版） ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔧 完全修正版初期化開始");
    
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません");
        return;
    }
    
    cards = shuffle(rawCards.slice());
    currentIndex = 0;
    showingAnswer = false;
    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    
    console.log("📊 カードデータ: " + cards.length + "枚");
    console.log("🎯 初期表示状態: 問題表示");
    
    prerenderAllCards();
    setupInstantEvents();
    setupInstantKeyboard();
    
    // 段階的検証
    setTimeout(() => {
        console.log("📊 1秒後の状況:");
        ultraVerifyAllStates();
    }, 1000);
    
    setTimeout(() => {
        console.log("📊 3秒後の状況:");
        debugStatus();
    }, 3000);
    
    console.log("🔧 完全修正版初期化完了");
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
                e.preventDefault();
                fixAllImages();
                break;
            case 'd':
                e.preventDefault();
                debugStatus();
                break;
            case 'n':
                // 核爆弾級修復
                e.preventDefault();
                nuclearReset();
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

// デバッグ用グローバル関数
window.debugStatus = debugStatus;
window.fixAllImages = fixAllImages;
window.nuclearReset = nuclearReset;
window.ultraVerifyAllStates = ultraVerifyAllStates;

console.log("🔧 完全修正版読み込み完了");