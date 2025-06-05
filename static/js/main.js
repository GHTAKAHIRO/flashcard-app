console.log("⚡ 瞬間応答対応 main.js が Render 上で動いています！");

// ========== 瞬間応答システム統合版 ==========

// 🚀 瞬間応答用グローバル変数
let isInstantProcessing = false;
let currentDisplayIndex = 0;
let totalCardsCount = 0;
let cardsArray = [];
let showingAnswer = false;
let cardStatus = {};
let isPracticeMode = false;

// 🎯 DOM要素キャッシュ
const domCache = {
    flashcard: null,
    knownBtn: null,
    unknownBtn: null,
    correctCount: null,
    incorrectCount: null,
    progressInfo: null
};

// ⚡ 瞬間切り替えシステム
class InstantSwitchSystem {
    constructor() {
        this.cardContainers = new Map();
        this.isReady = false;
        this.logQueue = [];
        this.batchTimer = null;
    }

    // 🚀 全カードを事前レンダリング
    prerenderAllCards(cards) {
        console.log(`⚡ ${cards.length}枚のカードを事前レンダリング中...`);
        
        // フラッシュカードエリアを相対配置に設定
        domCache.flashcard.style.position = 'relative';
        domCache.flashcard.innerHTML = '';
        
        cards.forEach((card, index) => {
            const cardContainer = this.createCardContainer(card, index);
            this.cardContainers.set(index, cardContainer);
            
            // 最初のカード以外は非表示
            if (index !== 0) {
                cardContainer.style.display = 'none';
            }
            
            domCache.flashcard.appendChild(cardContainer);
        });
        
        this.isReady = true;
        console.log(`🚀 事前レンダリング完了: ${cards.length}枚`);
    }

    // 📝 カードコンテナ作成
    createCardContainer(card, index) {
        const container = document.createElement('div');
        container.className = 'instant-card-container';
        container.dataset.cardIndex = index;
        container.dataset.cardId = card.id;
        
        // 🚀 絶対配置でオーバーレイ
        container.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            will-change: transform;
            transform: translateZ(0);
        `;

        // 問題表示部分
        const problemDiv = document.createElement('div');
        problemDiv.className = 'problem-container';
        problemDiv.style.cssText = 'display: block; width: 100%; text-align: center;';
        
        if (card.image_problem) {
            const img = document.createElement('img');
            img.src = card.image_problem;
            img.loading = 'eager';
            img.style.cssText = 'max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);';
            problemDiv.appendChild(img);
        }
        
        if (card.problem_number && card.topic) {
            const text = document.createElement('p');
            text.textContent = `${card.problem_number}: ${card.topic}`;
            text.style.cssText = 'margin: 15px 0 0 0; font-weight: bold; font-size: 16px; color: #333;';
            problemDiv.appendChild(text);
        }

        // 解答表示部分
        const answerDiv = document.createElement('div');
        answerDiv.className = 'answer-container';
        answerDiv.style.cssText = 'display: none; width: 100%; text-align: center;';
        
        if (card.image_answer) {
            const answerImg = document.createElement('img');
            answerImg.src = card.image_answer;
            answerImg.loading = 'eager';
            answerImg.style.cssText = 'max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);';
            answerDiv.appendChild(answerImg);
        }

        container.appendChild(problemDiv);
        container.appendChild(answerDiv);
        
        return container;
    }

    // ⚡ 瞬間カード切り替え（0-2ms）
    switchToCard(index) {
        if (!this.isReady || index >= this.cardContainers.size) {
            return false;
        }

        // 🚀 現在のカードを非表示
        const currentContainer = this.cardContainers.get(currentDisplayIndex);
        if (currentContainer) {
            currentContainer.style.display = 'none';
        }

        // 🚀 次のカードを表示
        const nextContainer = this.cardContainers.get(index);
        if (nextContainer) {
            nextContainer.style.display = 'flex';
            // 問題表示状態にリセット
            this.resetToProblemView(nextContainer);
        }

        currentDisplayIndex = index;
        this.updateProgress(index);
        
        return true;
    }

    // 📖 問題表示状態にリセット
    resetToProblemView(container) {
        const problemDiv = container.querySelector('.problem-container');
        const answerDiv = container.querySelector('.answer-container');
        
        if (problemDiv && answerDiv) {
            problemDiv.style.display = 'block';
            answerDiv.style.display = 'none';
        }
        showingAnswer = false;
    }

    // 🔄 解答表示切り替え
    toggleAnswer() {
        const currentContainer = this.cardContainers.get(currentDisplayIndex);
        if (!currentContainer) return;

        const problemDiv = currentContainer.querySelector('.problem-container');
        const answerDiv = currentContainer.querySelector('.answer-container');
        
        if (problemDiv && answerDiv) {
            showingAnswer = !showingAnswer;
            
            problemDiv.style.display = showingAnswer ? 'none' : 'block';
            answerDiv.style.display = showingAnswer ? 'block' : 'none';
        }
    }

    // 📊 進捗更新
    updateProgress(index) {
        if (domCache.progressInfo) {
            domCache.progressInfo.innerHTML = `<i class="fas fa-chart-line"></i> ${index + 1} / ${totalCardsCount}`;
        }
    }

    // 📝 現在のカードID取得
    getCurrentCardId() {
        const currentContainer = this.cardContainers.get(currentDisplayIndex);
        return currentContainer ? currentContainer.dataset.cardId : null;
    }

    // 📤 ログキューイング
    queueLog(result) {
        const cardId = this.getCurrentCardId();
        
        this.logQueue.push({
            card_id: cardId,
            result: result,
            stage: stage,
            mode: mode,
            timestamp: performance.now()
        });

        // デバウンス処理
        if (this.batchTimer) {
            clearTimeout(this.batchTimer);
        }

        this.batchTimer = setTimeout(() => {
            this.processBatchLogs();
        }, 100);
    }

    // 📤 バッチログ送信
    async processBatchLogs() {
        if (this.logQueue.length === 0) return;
        
        const currentBatch = [...this.logQueue];
        this.logQueue = [];

        try {
            const latestEntry = currentBatch[currentBatch.length - 1];
            
            const response = await fetch('/log_result', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(latestEntry)
            });

            const data = await response.json();
            
            if (data.redirect_to_prepare) {
                this.showMessage(data.message);
                setTimeout(() => {
                    window.location.href = `/prepare/${getCurrentSource()}`;
                }, 1000);
            }
        } catch (error) {
            console.error('ログ送信エラー:', error);
        }
    }

    // 💬 メッセージ表示
    showMessage(message) {
        const toast = document.createElement('div');
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #4CAF50;
            color: white;
            padding: 12px 20px;
            border-radius: 6px;
            font-weight: bold;
            z-index: 1000;
            transform: translateX(100%);
            transition: transform 0.3s ease;
        `;
        
        document.body.appendChild(toast);
        
        requestAnimationFrame(() => {
            toast.style.transform = 'translateX(0)';
        });
        
        setTimeout(() => {
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, 2000);
    }
}

// 🚀 瞬間システムインスタンス
const instantSystem = new InstantSwitchSystem();

// ========== 既存関数との統合 ==========

document.addEventListener('DOMContentLoaded', function () {
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません！");
        return;
    }

    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    
    // DOM要素キャッシュ初期化
    initializeDOMCache();
    
    // 瞬間システムで初期化
    initCards(rawCards);
    
    console.log('⚡ 瞬間応答システム初期化完了');
});

// 🚀 DOM要素キャッシュ初期化
function initializeDOMCache() {
    domCache.flashcard = document.getElementById('flashcard');
    domCache.knownBtn = document.getElementById('knownBtn');
    domCache.unknownBtn = document.getElementById('unknownBtn');
    domCache.correctCount = document.getElementById('correct-count');
    domCache.incorrectCount = document.getElementById('incorrect-count');
    domCache.progressInfo = document.getElementById('progress-info');
}

function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

function initCards(data) {
    cardsArray = shuffle(data.slice());
    totalCardsCount = cardsArray.length;
    currentDisplayIndex = 0;
    showingAnswer = false;
    cardStatus = {};
    
    // 🚀 瞬間システムで事前レンダリング
    instantSystem.prerenderAllCards(cardsArray);
    
    // 🚀 イベントリスナー設定
    if (domCache.knownBtn) {
        domCache.knownBtn.addEventListener('click', () => 
            handleInstantAnswer('known', domCache.knownBtn)
        );
    }
    
    if (domCache.unknownBtn) {
        domCache.unknownBtn.addEventListener('click', () => 
            handleInstantAnswer('unknown', domCache.unknownBtn)
        );
    }
    
    if (domCache.flashcard) {
        domCache.flashcard.addEventListener('click', toggleAnswerInstant);
    }
    
    // キーボード設定
    setupInstantKeyboard();
}

// ⚡ 瞬間応答処理（1-3ms以内）
function handleInstantAnswer(result, element) {
    if (isInstantProcessing) return;
    isInstantProcessing = true;

    // 🚀 STEP 1: 瞬間ボタンフィードバック（同期、<1ms）
    triggerInstantButtonFeedback(element, result);

    // 🚀 STEP 2: 瞬間カウンター更新（同期、<1ms）
    updateCounterInstantly(result);

    // 🚀 STEP 3: 瞬間次カード表示（同期、1-2ms）
    const success = instantSystem.switchToCard(currentDisplayIndex + 1);

    if (!success) {
        // カード終了処理
        handleInstantCompletion();
        return;
    }

    // 🚀 STEP 4: 非同期ログ処理（バックグラウンド）
    instantSystem.queueLog(result);

    // 🚀 処理完了
    isInstantProcessing = false;
}

// ⚡ 瞬間ボタンフィードバック
function triggerInstantButtonFeedback(element, result) {
    element.style.transform = 'scale(0.95)';
    element.style.backgroundColor = result === 'known' ? '#45a049' : '#da190b';
    
    requestAnimationFrame(() => {
        element.style.transform = 'scale(1)';
        setTimeout(() => {
            element.style.backgroundColor = '';
        }, 80);
    });
}

// ⚡ 瞬間カウンター更新
function updateCounterInstantly(result) {
    if (result === 'known' && domCache.correctCount) {
        const current = parseInt(domCache.correctCount.textContent) || 0;
        domCache.correctCount.textContent = current + 1;
    } else if (result === 'unknown' && domCache.incorrectCount) {
        const current = parseInt(domCache.incorrectCount.textContent) || 0;
        domCache.incorrectCount.textContent = current + 1;
    }
}

// ⚡ 瞬間完了処理
function handleInstantCompletion() {
    instantSystem.showMessage("✅ 完了しました！");
    
    setTimeout(() => {
        if (isPracticeMode) {
            window.location.reload();
        } else {
            window.location.href = `/prepare/${getCurrentSource()}`;
        }
    }, 1000);
}

// ⚡ 瞬間解答切り替え
function toggleAnswerInstant() {
    instantSystem.toggleAnswer();
}

// 🎹 瞬間キーボード処理
function setupInstantKeyboard() {
    document.addEventListener('keydown', (e) => {
        if (isInstantProcessing) return;

        switch(e.key.toLowerCase()) {
            case 'j':
            case 'arrowleft':
                e.preventDefault();
                handleInstantAnswer('known', domCache.knownBtn);
                break;
            case 'f':
            case 'arrowright':
                e.preventDefault();
                handleInstantAnswer('unknown', domCache.unknownBtn);
                break;
            case ' ':
                e.preventDefault();
                toggleAnswerInstant();
                break;
        }
    });
}

// ========== 既存関数との互換性維持 ==========

function renderCard() {
    // 瞬間システムでは事前レンダリング済みなので何もしない
    console.log('[RENDERCARD] 瞬間システムでは事前レンダリング済み');
}

function toggleAnswer() {
    toggleAnswerInstant();
}

function markKnown() {
    handleInstantAnswer('known', domCache.knownBtn);
}

function markUnknown() {
    handleInstantAnswer('unknown', domCache.unknownBtn);
}

function nextCard() {
    // 瞬間システムでは自動で次カードに進んでいる
    console.log('[NEXTCARD] 瞬間システムで自動処理済み');
}

function nextCardFast() {
    nextCard();
}

function handleAnswer(result, element) {
    handleInstantAnswer(result, element);
}

function handleAnswerFast(result) {
    const element = result === 'known' ? domCache.knownBtn : domCache.unknownBtn;
    handleInstantAnswer(result, element);
}

function handleAnswerUltraFast(result, element) {
    handleInstantAnswer(result, element);
}

function loadNextCard() {
    console.log('[LOADNEXTCARD] 瞬間システムで自動処理済み');
}

function loadNextCardFast() {
    loadNextCard();
}

function updateCounters(result) {
    updateCounterInstantly(result);
}

function updateCountersUltraFast(result) {
    updateCounterInstantly(result);
}

function showToast(message, type = "info") {
    instantSystem.showMessage(message);
}

function showToastUltraFast(message, type = "info") {
    instantSystem.showMessage(message);
}

function showMessage(message, type = "info") {
    instantSystem.showMessage(message);
}

function preloadNextCards() {
    // 瞬間システムでは事前レンダリング済み
    console.log('[PRELOAD] 瞬間システムでは事前レンダリング済み');
}

function preloadNextCardsUltraFast() {
    preloadNextCards();
}

// 既存のsendResult関数（互換性）
async function sendResult(cardId, result) {
    // 瞬間システムではキューイングで処理
    console.log('[SENDRESULT] 瞬間システムではキューイングで処理済み');
    return Promise.resolve({ status: 'ok' });
}

async function sendResultFast(cardId, result) {
    return sendResult(cardId, result);
}

async function sendResultUltraFast(cardId, result) {
    return sendResult(cardId, result);
}

async function logResultUltraFast(result) {
    // 瞬間システムではキューイングで処理
    return sendResult(null, result);
}

// 🔧 ユーティリティ関数
function getCurrentSource() {
    const pathParts = window.location.pathname.split('/');
    return pathParts[pathParts.length - 1];
}

// 🚀 CSS最適化（瞬間切り替え用）
function addInstantStyles() {
    if (!document.getElementById('instant-styles')) {
        const style = document.createElement('style');
        style.id = 'instant-styles';
        style.textContent = `
            /* ⚡ 瞬間切り替え最適化 */
            #flashcard {
                min-height: 450px;
                position: relative !important;
                overflow: hidden;
            }
            
            .instant-card-container {
                transition: none !important;
                animation: none !important;
            }
            
            .instant-card-container img {
                image-rendering: -webkit-optimize-contrast;
                image-rendering: crisp-edges;
                image-rendering: auto;
            }
            
            /* ⚡ ボタン最適化 */
            #knownBtn, #unknownBtn {
                will-change: transform, background-color;
                transform: translateZ(0);
                transition: all 0.05s ease !important;
            }
            
            #knownBtn:active, #unknownBtn:active {
                transform: scale(0.95) !important;
            }
            
            /* ⚡ カウンター最適化 */
            #correct-count, #incorrect-count {
                will-change: contents;
                font-variant-numeric: tabular-nums;
            }
            
            /* ⚡ 進捗表示最適化 */
            #progress-info {
                will-change: contents;
                font-variant-numeric: tabular-nums;
            }
            
            /* ⚡ GPU加速 */
            .problem-container, .answer-container {
                will-change: transform;
                transform: translateZ(0);
            }
            
            /* ⚡ レイアウトシフト防止 */
            .instant-card-container p {
                margin: 15px 0 0 0 !important;
                line-height: 1.4;
            }
            
            /* ⚡ 画像読み込み最適化 */
            .instant-card-container img {
                max-width: 100%;
                height: auto;
                display: block;
                margin: 0 auto;
                border-radius: 8px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }
        `;
        document.head.appendChild(style);
    }
}

// 🚀 パフォーマンス監視
function startInstantPerformanceMonitoring() {
    let clickStartTime = 0;
    
    document.addEventListener('mousedown', (e) => {
        if (e.target.id === 'knownBtn' || e.target.id === 'unknownBtn') {
            clickStartTime = performance.now();
        }
    });
    
    // カード切り替え完了を監視
    const observer = new MutationObserver(() => {
        if (clickStartTime > 0) {
            const responseTime = performance.now() - clickStartTime;
            console.log(`⚡ 瞬間応答時間: ${responseTime.toFixed(2)}ms`);
            
            if (responseTime < 10) {
                console.log('🚀 瞬間応答達成！(10ms未満)');
            } else if (responseTime < 20) {
                console.log('🏃 高速応答達成！(20ms未満)');
            }
            
            clickStartTime = 0;
        }
    });
    
    if (domCache.flashcard) {
        observer.observe(domCache.flashcard, { 
            childList: true, 
            subtree: true,
            attributes: true,
            attributeFilter: ['style']
        });
    }
}

// 🚀 初期化統合
function initializeInstantOptimization() {
    addInstantStyles();
    startInstantPerformanceMonitoring();
    
    // メモリ最適化
    setInterval(() => {
        if (window.gc && typeof window.gc === 'function') {
            window.gc();
        }
    }, 30000);
    
    console.log('⚡ 瞬間システム完全初期化完了');
    console.log('🎯 目標応答時間: <5ms (クリック同時)');
}

// ⚡ DOMContentLoaded時の追加初期化
document.addEventListener('DOMContentLoaded', function() {
    // 少し遅延させて他の初期化完了後に実行
    setTimeout(() => {
        initializeInstantOptimization();
    }, 100);
});

console.log('⚡ 瞬間応答対応 main.js 読み込み完了 - クリック同時切り替え実装'); '