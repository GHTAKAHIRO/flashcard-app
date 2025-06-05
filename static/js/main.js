console.log("🚀 main.js が Render 上で動いています！");

// ⚡ 超高速化グローバル変数
let isProcessing = false;
let nextCardPreloaded = false;
let optimisticNextIndex = 0;
let logBatch = [];
let batchTimer = null;

// 既存のプリロード管理クラス（高速化版）
class UltraFastImagePreloader {
    constructor() {
        this.preloadedImages = new Map();
        this.preloadContainer = this.createPreloadContainer();
    }

    createPreloadContainer() {
        const container = document.createElement('div');
        container.id = 'preload-container';
        container.style.cssText = 'position:absolute;left:-9999px;top:-9999px;opacity:0;pointer-events:none;';
        document.body.appendChild(container);
        return container;
    }

    preloadNext(cardData) {
        if (!cardData || this.preloadedImages.has(cardData.id)) return;

        // ⚡ 並列プリロード
        return new Promise((resolve) => {
            const problemImg = new Image();
            const answerImg = new Image();
            
            let loadedCount = 0;
            const checkComplete = () => {
                loadedCount++;
                if (loadedCount === 2) {
                    this.preloadedImages.set(cardData.id, {
                        problem: problemImg.src,
                        answer: answerImg.src
                    });
                    resolve();
                }
            };
            
            problemImg.onload = checkComplete;
            problemImg.onerror = checkComplete;
            answerImg.onload = checkComplete;
            answerImg.onerror = checkComplete;
            
            problemImg.loading = 'eager';
            answerImg.loading = 'eager';
            problemImg.src = cardData.image_problem;
            answerImg.src = cardData.image_answer;
            
            this.preloadContainer.appendChild(problemImg);
            this.preloadContainer.appendChild(answerImg);
        });
    }
}

const ultraFastPreloader = new UltraFastImagePreloader();

document.addEventListener('DOMContentLoaded', function () {
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません！");
        return;
    }

    // ⚡ 超高速イベントリスナー
    document.getElementById('flashcard').addEventListener('click', toggleAnswerUltraFast);
    document.getElementById('knownBtn').addEventListener('click', () => handleAnswerUltraFast('known', document.getElementById('knownBtn')));
    document.getElementById('unknownBtn').addEventListener('click', () => handleAnswerUltraFast('unknown', document.getElementById('unknownBtn')));

    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    initCards(rawCards);
    
    // ⚡ 超高速化初期化
    setupUltraFastKeyboard();
    console.log('⚡ 超高速化システム初期化完了');
});

let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};
let isPracticeMode = false;

function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

function initCards(data) {
    cards = shuffle(data.slice());
    currentIndex = 0;
    optimisticNextIndex = 0;
    showingAnswer = false;
    cardStatus = {};
    renderCardUltraFast();
    
    // ⚡ 次の5枚を並列プリロード
    preloadNextCardsUltraFast();
}

// ⚡ 超高速カードレンダリング
function renderCardUltraFast() {
    const card = cards[currentIndex];
    const cardDiv = document.getElementById('flashcard');
    
    // ⚡ DOM更新最小化
    cardDiv.style.opacity = '0.8';
    
    // DocumentFragmentで一括DOM操作
    const fragment = document.createDocumentFragment();
    
    const questionDiv = document.createElement('div');
    questionDiv.id = 'problem-container';
    
    if (card.image_problem) {
        const img = document.createElement('img');
        img.id = 'problem-image';
        img.src = card.image_problem;
        img.dataset.cardId = card.id;
        img.loading = 'eager';
        img.style.cssText = 'max-width: 100%; height: auto; display: block;';
        questionDiv.appendChild(img);
    }
    
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = `${card.problem_number}: ${card.topic}`;
        text.style.cssText = 'margin: 10px 0; font-weight: bold; text-align: center;';
        questionDiv.appendChild(text);
    }

    fragment.appendChild(questionDiv);

    // ⚡ 解答部分も事前準備
    if (card.image_answer) {
        const answerDiv = document.createElement('div');
        answerDiv.id = 'answer-container';
        answerDiv.style.display = showingAnswer ? 'block' : 'none';
        
        const answerImg = document.createElement('img');
        answerImg.id = 'answer-image';
        answerImg.src = card.image_answer;
        answerImg.loading = 'eager';
        answerImg.style.cssText = 'max-width: 100%; height: auto; display: block;';
        answerDiv.appendChild(answerImg);
        
        fragment.appendChild(answerDiv);
    }
    
    // ⚡ 一括DOM更新
    cardDiv.innerHTML = '';
    cardDiv.appendChild(fragment);
    
    // ⚡ スムーズ表示（GPU加速）
    requestAnimationFrame(() => {
        cardDiv.style.opacity = '1';
    });
    
    // 進捗更新
    updateProgressDisplayUltraFast();
}

// ⚡ 超高速解答切り替え
function toggleAnswerUltraFast() {
    showingAnswer = !showingAnswer;
    
    const problemContainer = document.getElementById('problem-container');
    const answerContainer = document.getElementById('answer-container');
    
    if (problemContainer && answerContainer) {
        // ⚡ CSS transitionを一時無効化
        problemContainer.style.transition = 'none';
        answerContainer.style.transition = 'none';
        
        if (showingAnswer) {
            problemContainer.style.display = 'none';
            answerContainer.style.display = 'block';
        } else {
            problemContainer.style.display = 'block';
            answerContainer.style.display = 'none';
        }
        
        // 次フレームでtransition復活
        requestAnimationFrame(() => {
            problemContainer.style.transition = '';
            answerContainer.style.transition = '';
        });
    }
}

// ⚡ 超高速回答処理（メイン関数）
function handleAnswerUltraFast(result, element) {
    if (isProcessing) return;
    isProcessing = true;
    
    // ========== 瞬間UI更新（1-3ms） ==========
    updateUIInstantly(result, element);
    
    // ========== 楽観的次カード表示（5-10ms） ==========
    optimisticCardAdvance();
    
    // ========== バックグラウンドでログ処理（0ms待機） ==========
    requestIdleCallback(() => {
        logResultUltraFast(result).finally(() => {
            isProcessing = false;
        });
    });
}

// ⚡ 瞬間UI更新
function updateUIInstantly(result, element) {
    // GPU加速アニメーション
    element.style.willChange = 'transform';
    element.style.transform = 'scale3d(0.95, 0.95, 1)';
    element.style.backgroundColor = result === 'known' ? '#45a049' : '#da190b';
    
    // カウンター即座更新
    updateCountersUltraFast(result);
    
    // 次フレームで元に戻す
    requestAnimationFrame(() => {
        element.style.transform = 'scale3d(1, 1, 1)';
        element.style.willChange = 'auto';
        setTimeout(() => {
            element.style.backgroundColor = '';
        }, 100);
    });
}

function updateCountersUltraFast(result) {
    const correctSpan = document.getElementById('correct-count');
    const incorrectSpan = document.getElementById('incorrect-count');
    
    if (result === 'known' && correctSpan) {
        correctSpan.textContent = parseInt(correctSpan.textContent || '0') + 1;
    } else if (result === 'unknown' && incorrectSpan) {
        incorrectSpan.textContent = parseInt(incorrectSpan.textContent || '0') + 1;
    }
}

// ⚡ 楽観的次カード表示
function optimisticCardAdvance() {
    const id = cards[currentIndex].id;
    currentIndex++;
    optimisticNextIndex = currentIndex;

    if (currentIndex >= cards.length) {
        // カード終了処理
        handleCardEndUltraFast();
        return;
    }

    showingAnswer = false;
    renderCardUltraFast();
    
    // さらに次のカードをプリロード
    preloadNextCardsUltraFast();
}

// ⚡ 超高速プリロード
function preloadNextCardsUltraFast() {
    const preloadPromises = [];
    
    for (let i = 1; i <= 3; i++) {
        const nextIndex = currentIndex + i;
        if (nextIndex < cards.length) {
            const nextCard = cards[nextIndex];
            if (nextCard) {
                preloadPromises.push(ultraFastPreloader.preloadNext(nextCard));
            }
        }
    }
    
    Promise.allSettled(preloadPromises);
}

function updateProgressDisplayUltraFast() {
    const progressElement = document.getElementById('progress-info');
    if (progressElement) {
        progressElement.innerHTML = `<i class="fas fa-chart-line"></i> ${currentIndex + 1} / ${cards.length}`;
    }
}

// ⚡ 超高速ログ処理（バッチ処理）
async function logResultUltraFast(result) {
    const cardId = cards[currentIndex - 1]?.id; // 既に次に進んでいるので-1
    
    const logEntry = {
        card_id: cardId,
        result: result,
        stage: stage,
        mode: mode,
        timestamp: Date.now()
    };
    
    logBatch.push(logEntry);
    
    // ⚡ デバウンス処理（50ms）
    if (batchTimer) {
        clearTimeout(batchTimer);
    }
    
    batchTimer = setTimeout(async () => {
        const currentBatch = [...logBatch];
        logBatch = [];
        
        try {
            const latestEntry = currentBatch[currentBatch.length - 1];
            
            const response = await fetch('/log_result', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(latestEntry)
            });

            const data = await response.json();
            
            if (data.status === 'ok') {
                handleLogSuccessUltraFast(data);
            }
        } catch (error) {
            console.error('[SUBMIT] エラー:', error);
        }
    }, 50);
}

// ⚡ 超高速成功処理
function handleLogSuccessUltraFast(data) {
    if (data.redirect_to_prepare) {
        showToastUltraFast(data.message, 'success');
        setTimeout(() => {
            const currentSource = getCurrentSource();
            window.location.href = `/prepare/${currentSource}`;
        }, 800);
    }
}

function handleCardEndUltraFast() {
    console.log('[NEXTCARD] カード終了:', currentIndex, '/', cards.length);
    
    if (isPracticeMode) {
        showToastUltraFast("問題を読み込んでいます...", 'info');
        setTimeout(() => {
            window.location.reload();
        }, 1000);
    } else {
        showToastUltraFast("✅ テスト完了！", 'success');
        setTimeout(() => {
            const currentSource = getCurrentSource();
            window.location.href = `/prepare/${currentSource}`;
        }, 800);
    }
}

// ⚡ 超高速トースト
function showToastUltraFast(message, type = 'info') {
    const existingToast = document.getElementById('speedToast');
    if (existingToast) {
        existingToast.remove();
    }
    
    const toast = document.createElement('div');
    toast.id = 'speedToast';
    toast.textContent = message;
    
    Object.assign(toast.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        padding: '12px 20px',
        borderRadius: '6px',
        color: 'white',
        fontWeight: 'bold',
        zIndex: '1000',
        maxWidth: '300px',
        fontSize: '14px',
        background: type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3',
        transform: 'translateX(100%)',
        transition: 'transform 0.2s ease'
    });
    
    document.body.appendChild(toast);
    
    requestAnimationFrame(() => {
        toast.style.transform = 'translateX(0)';
    });
    
    setTimeout(() => {
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 200);
    }, type === 'success' ? 700 : 1500);
}

// ⚡ 超高速キーボード
function setupUltraFastKeyboard() {
    let keyDownTime = {};
    
    document.addEventListener('keydown', (e) => {
        if (isProcessing) return;
        
        const key = e.key.toLowerCase();
        const now = performance.now();
        
        // ⚡ キーリピート防止（高速連打対応）
        if (keyDownTime[key] && now - keyDownTime[key] < 100) {
            return;
        }
        keyDownTime[key] = now;
        
        switch(key) {
            case 'j':
            case 'arrowleft':
                e.preventDefault();
                handleAnswerUltraFast('known', document.getElementById('knownBtn'));
                break;
            case 'f':
            case 'arrowright':
                e.preventDefault();
                handleAnswerUltraFast('unknown', document.getElementById('unknownBtn'));
                break;
            case ' ':
                e.preventDefault();
                toggleAnswerUltraFast();
                break;
        }
    });
}

// 既存関数の互換性維持
function getCurrentSource() {
    const pathParts = window.location.pathname.split('/');
    const source = pathParts[pathParts.length - 1];
    return source;
}

// 後方互換性のための関数
function markKnown() {
    handleAnswerUltraFast('known', document.getElementById('knownBtn'));
}

function markUnknown() {
    handleAnswerUltraFast('unknown', document.getElementById('unknownBtn'));
}

function nextCard() {
    // 楽観的更新で既に処理済み
    console.log('[NEXTCARD] 楽観的更新で処理済み');
}

function nextCardFast() {
    nextCard();
}

function renderCard() {
    renderCardUltraFast();
}

function toggleAnswer() {
    toggleAnswerUltraFast();
}

function showToast(message, type = "info") {
    showToastUltraFast(message, type);
}

function showMessage(message, type = "info") {
    showToastUltraFast(message, type);
}

// 既存のsendResult関数（互換性）
async function sendResult(cardId, result) {
    // 新しいシステムでは楽観的更新で処理済み
    console.log('[SENDRESULT] 互換性関数 - 楽観的更新で処理済み');
    return Promise.resolve({ status: 'ok' });
}

async function sendResultFast(cardId, result) {
    return sendResult(cardId, result);
}

function handleAnswer(result, element) {
    handleAnswerUltraFast(result, element);
}

function handleAnswerFast(result) {
    const element = result === 'known' ? 
        document.getElementById('knownBtn') : 
        document.getElementById('unknownBtn');
    handleAnswerUltraFast(result, element);
}

function loadNextCard() {
    // 楽観的更新で既に処理済み
    console.log('[LOADNEXTCARD] 楽観的更新で処理済み');
}

function loadNextCardFast() {
    loadNextCard();
}

function updateCounters(result) {
    updateCountersUltraFast(result);
}

function preloadNextCards() {
    preloadNextCardsUltraFast();
}

// ⚡ CSS最適化スタイル追加
function addUltraFastStyles() {
    if (!document.getElementById('ultra-fast-styles')) {
        const style = document.createElement('style');
        style.id = 'ultra-fast-styles';
        style.textContent = `
            /* ⚡ GPU加速最適化 */
            #flashcard {
                will-change: opacity;
                transform: translateZ(0);
            }
            
            #knownBtn, #unknownBtn {
                will-change: transform, background-color;
                transform: translateZ(0);
            }
            
            #problem-container, #answer-container {
                will-change: transform;
                transform: translateZ(0);
            }
            
            /* ⚡ 高速切り替え用 */
            .no-transition {
                transition: none !important;
            }
            
            /* ⚡ 画像読み込み最適化 */
            img {
                image-rendering: -webkit-optimize-contrast;
                image-rendering: crisp-edges;
            }
            
            /* ⚡ ボタン応答性向上 */
            #knownBtn:active, #unknownBtn:active {
                transform: scale3d(0.95, 0.95, 1) !important;
                transition: transform 0.05s ease !important;
            }
            
            /* ⚡ リフロー削減 */
            .card-info span {
                display: inline-block;
                will-change: contents;
            }
            
            /* ⚡ プリロード画像最適化 */
            #preload-container img {
                position: absolute;
                width: 1px;
                height: 1px;
                opacity: 0;
                pointer-events: none;
            }
        `;
        document.head.appendChild(style);
    }
}

// ⚡ パフォーマンス監視
function startPerformanceMonitoring() {
    let clickStartTime = 0;
    
    document.addEventListener('mousedown', (e) => {
        if (e.target.id === 'knownBtn' || e.target.id === 'unknownBtn') {
            clickStartTime = performance.now();
        }
    });
    
    document.addEventListener('mouseup', (e) => {
        if (e.target.id === 'knownBtn' || e.target.id === 'unknownBtn') {
            const responseTime = performance.now() - clickStartTime;
            console.log(`⚡ ボタン応答時間: ${responseTime.toFixed(2)}ms`);
            
            // 50ms以下なら成功
            if (responseTime < 50) {
                console.log('🚀 超高速応答達成！');
            }
        }
    });
}

// ⚡ メモリ最適化
function optimizeMemory() {
    // 不要なイベントリスナー削除
    const oldListeners = document.querySelectorAll('[onclick]');
    oldListeners.forEach(el => {
        el.removeAttribute('onclick');
    });
    
    // 定期的なガベージコレクション促進
    setInterval(() => {
        if (window.gc && typeof window.gc === 'function') {
            window.gc();
        }
    }, 60000); // 1分毎
}

// ⚡ 初期化統合
function initializeUltraFastSystem() {
    addUltraFastStyles();
    optimizeMemory();
    startPerformanceMonitoring();
    
    // Web Workers対応チェック
    if (typeof Worker !== 'undefined') {
        console.log('⚡ Web Workers利用可能');
    }
    
    // 画像デコード最適化
    if ('decode' in HTMLImageElement.prototype) {
        console.log('⚡ 画像デコード最適化利用可能');
    }
    
    // Intersection Observer対応
    if ('IntersectionObserver' in window) {
        console.log('⚡ Intersection Observer利用可能');
    }
    
    console.log('⚡ 超高速システム完全初期化完了');
    console.log('🎯 期待される応答時間: <20ms');
}

// ⚡ DOMContentLoaded時の初期化に追加
document.addEventListener('DOMContentLoaded', function() {
    initializeUltraFastSystem();
});

console.log('📈 超高速対応 main.js 読み込み完了');