console.log("🚀 main.js が Render 上で動いています！");

// 🚀 高速化システム追加
let isProcessing = false;
const DEBOUNCE_TIME = 100;

// プリロード管理クラス
class FastImagePreloader {
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

        const problemImg = document.createElement('img');
        const answerImg = document.createElement('img');
        
        problemImg.onload = () => {
            this.preloadedImages.set(cardData.id, {
                problem: problemImg.src,
                answer: answerImg.src
            });
        };
        
        problemImg.src = cardData.image_problem;
        if (cardData.image_answer) {
            answerImg.src = cardData.image_answer;
        }
        
        this.preloadContainer.appendChild(problemImg);
        this.preloadContainer.appendChild(answerImg);
    }
}

const fastPreloader = new FastImagePreloader();

document.addEventListener('DOMContentLoaded', function () {
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません！");
        return;
    }

    // 🚀 高速化されたイベントリスナー
    document.getElementById('flashcard').addEventListener('click', toggleAnswer);
    document.getElementById('knownBtn').addEventListener('click', () => handleAnswerFast('known'));
    document.getElementById('unknownBtn').addEventListener('click', () => handleAnswerFast('unknown'));

    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    initCards(rawCards);
    
    // 🚀 高速化初期化
    setupKeyboardShortcuts();
    addSpeedStyles();
    console.log('🚀 高速化システム初期化完了');
});

let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};  // id => 'known' or 'unknown'
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
    showingAnswer = false;
    cardStatus = {};
    renderCard();
    
    // 🚀 次の3枚をプリロード
    preloadNextCards();
}

// 🚀 高速化されたrenderCard関数
function renderCard() {
    const card = cards[currentIndex];
    const cardDiv = document.getElementById('flashcard');
    
    // 🚀 DOM操作を最小限に
    cardDiv.style.opacity = '0.7';
    cardDiv.innerHTML = '';

    const questionDiv = document.createElement('div');
    questionDiv.id = 'problem-container';
    
    if (card.image_problem) {
        const img = document.createElement('img');
        img.id = 'problem-image';
        img.src = card.image_problem;
        img.dataset.cardId = card.id;
        img.style.cssText = 'max-width: 100%; height: auto; display: block;';
        img.loading = 'eager'; // 高速読み込み
        questionDiv.appendChild(img);
    }
    
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = `${card.problem_number}: ${card.topic}`;
        text.style.cssText = 'margin: 10px 0; font-weight: bold; text-align: center;';
        questionDiv.appendChild(text);
    }

    cardDiv.appendChild(questionDiv);

    // 🚀 解答部分も事前準備
    if (card.image_answer) {
        const answerDiv = document.createElement('div');
        answerDiv.id = 'answer-container';
        answerDiv.style.display = showingAnswer ? 'block' : 'none';
        
        const answerImg = document.createElement('img');
        answerImg.id = 'answer-image';
        answerImg.src = card.image_answer;
        answerImg.style.cssText = 'max-width: 100%; height: auto; display: block;';
        answerDiv.appendChild(answerImg);
        
        cardDiv.appendChild(answerDiv);
    }
    
    // 🚀 スムーズな表示
    setTimeout(() => {
        cardDiv.style.opacity = '1';
    }, 50);
    
    // カウンター更新
    updateProgressDisplay();
}

// 🚀 高速化されたtoggleAnswer
function toggleAnswer() {
    showingAnswer = !showingAnswer;
    
    const problemContainer = document.getElementById('problem-container');
    const answerContainer = document.getElementById('answer-container');
    
    if (problemContainer && answerContainer) {
        // 🚀 即座に切り替え（transitionなし）
        if (showingAnswer) {
            problemContainer.style.display = 'none';
            answerContainer.style.display = 'block';
        } else {
            problemContainer.style.display = 'block';
            answerContainer.style.display = 'none';
        }
    } else {
        // フォールバック：既存方式
        renderCard();
    }
}

// 🚀 新しい高速化された回答処理
function handleAnswerFast(result) {
    if (isProcessing) return;
    isProcessing = true;
    
    // 🚀 即座にUI更新
    updateUIImmediately(result);
    
    // 🚀 非同期でログ処理
    setTimeout(() => {
        const id = cards[currentIndex].id;
        cardStatus[id] = result;
        sendResultFast(id, result).finally(() => {
            isProcessing = false;
        });
    }, 0);
}

function updateUIImmediately(result) {
    // ボタンフィードバック
    const button = result === 'known' ? 
        document.getElementById('knownBtn') : 
        document.getElementById('unknownBtn');
    
    if (button) {
        button.style.transform = 'scale(0.95)';
        button.style.backgroundColor = result === 'known' ? '#45a049' : '#da190b';
        
        setTimeout(() => {
            button.style.transform = 'scale(1)';
            button.style.backgroundColor = '';
        }, 150);
    }
    
    // カウンター更新
    updateCounters(result);
}

function updateCounters(result) {
    const correctSpan = document.getElementById('correct-count');
    const incorrectSpan = document.getElementById('incorrect-count');
    
    if (result === 'known' && correctSpan) {
        correctSpan.textContent = parseInt(correctSpan.textContent || '0') + 1;
    } else if (result === 'unknown' && incorrectSpan) {
        incorrectSpan.textContent = parseInt(incorrectSpan.textContent || '0') + 1;
    }
}

function updateProgressDisplay() {
    // 進捗表示の更新
    const progressElement = document.getElementById('progress-info');
    if (progressElement) {
        progressElement.textContent = `${currentIndex + 1} / ${cards.length}`;
    }
}

// 🚀 高速化されたsendResult
async function sendResultFast(cardId, result) {
    try {
        console.log('[SUBMIT] 回答送信開始:', cardId, result, 'mode:', mode);
        
        const response = await fetch('/log_result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_id: cardId,
                result: result,
                stage: stage,
                mode: mode
            })
        });

        const data = await response.json();
        console.log('[SUBMIT] レスポンス受信:', data);

        if (data.status === 'ok') {
            // 🔥 テストモード完了判定
            if (data.chunk_test_completed || data.stage_test_completed) {
                console.log('[SUBMIT] テスト完了:', data);
                
                if (data.redirect_to_prepare) {
                    console.log('[SUBMIT] prepare画面に戻ります');
                    showToast(data.message, 'success');
                    setTimeout(() => {
                        const currentSource = getCurrentSource();
                        window.location.href = `/prepare/${currentSource}`;
                    }, 1500);
                    return;
                }
            }
            
            // 🔥 練習モード完了判定
            if (data.practice_completed) {
                console.log('[SUBMIT] 練習完了:', data);
                
                if (data.redirect_to_prepare) {
                    console.log('[SUBMIT] prepare画面に戻ります');
                    showToast(data.message, 'success');
                    setTimeout(() => {
                        const currentSource = getCurrentSource();
                        window.location.href = `/prepare/${currentSource}`;
                    }, 1500);
                    return;
                }
            }
            
            // 🔥 練習モード継続判定
            if (data.practice_continuing) {
                console.log('[SUBMIT] 練習継続:', data.remaining_count, '問残り');
                showToast(data.message, 'info');
                
                // 🔥 重要：prepare画面に戻らず、次の問題へ
                setTimeout(() => {
                    nextCardFast();
                }, 800);
                return;
            }
            
            // 🔥 通常の次の問題へ（テストモード）
            console.log('[SUBMIT] 通常の次問題へ');
            nextCardFast();
            
        } else {
            throw new Error(data.message || '回答の送信に失敗しました');
        }

    } catch (error) {
        console.error('[SUBMIT] エラー:', error);
        showToast("❌ サーバーへの記録に失敗しました", "error");
        nextCardFast(); // エラーでも次に進む
    }
}

// 🚀 高速化されたnextCard
function nextCardFast() {
    currentIndex++;

    if (currentIndex >= cards.length) {
        console.log('[NEXTCARD] カード終了:', currentIndex, '/', cards.length);
        
        if (isPracticeMode) {
            console.log('[NEXTCARD] 練習モード - サーバーから新しいカードを待機');
            showToast("問題を読み込んでいます...", 'info');
            
            setTimeout(() => {
                window.location.reload();
            }, 1000);
            return;
        } else {
            console.log('[NEXTCARD] テストモード完了 - prepare画面に戻る');
            showToast("✅ テスト完了！", 'success');
            setTimeout(() => {
                const currentSource = getCurrentSource();
                window.location.href = `/prepare/${currentSource}`;
            }, 1500);
            return;
        }
    }

    showingAnswer = false;
    renderCard();
    
    // 🚀 次のカードもプリロード
    preloadNextCards();
}

function preloadNextCards() {
    // 次の3枚をプリロード
    for (let i = 1; i <= 3; i++) {
        const nextIndex = currentIndex + i;
        if (nextIndex < cards.length) {
            const nextCard = cards[nextIndex];
            if (nextCard) {
                fastPreloader.preloadNext(nextCard);
            }
        }
    }
}

// 🚀 高速トースト表示
function showToast(message, type = "info") {
    console.log('[TOAST]', type, ':', message);
    
    // 既存のトーストを削除
    const existingToast = document.getElementById('speedToast');
    if (existingToast) {
        existingToast.remove();
    }
    
    const toast = document.createElement('div');
    toast.id = 'speedToast';
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 6px;
        color: white;
        font-weight: bold;
        z-index: 1000;
        animation: slideIn 0.3s ease;
        max-width: 300px;
        background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, type === 'success' ? 1200 : 2000);
}

// 既存のshowMessage関数（後方互換性のため保持）
function showMessage(message, type = "info") {
    showToast(message, type);
}

function getCurrentSource() {
    const pathParts = window.location.pathname.split('/');
    const source = pathParts[pathParts.length - 1];
    console.log('[SOURCE] 現在の教材:', source);
    return source;
}

// 既存のmarkKnown/markUnknown（後方互換性のため保持）
function markKnown() {
    handleAnswerFast('known');
}

function markUnknown() {
    handleAnswerFast('unknown');
}

// 既存のnextCard関数（後方互換性のため保持）
function nextCard() {
    nextCardFast();
}

// 既存のsendResult関数（後方互換性のため保持）
async function sendResult(cardId, result) {
    return sendResultFast(cardId, result);
}

// 🚀 キーボードショートカット
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        if (isProcessing) return;
        
        switch(e.key.toLowerCase()) {
            case 'j':
            case 'arrowleft':
                e.preventDefault();
                handleAnswerFast('known');
                break;
            case 'f':
            case 'arrowright':
                e.preventDefault();
                handleAnswerFast('unknown');
                break;
            case ' ':
                e.preventDefault();
                toggleAnswer();
                break;
        }
    });
}

// 🚀 スタイル追加
function addSpeedStyles() {
    if (!document.getElementById('speed-styles')) {
        const style = document.createElement('style');
        style.id = 'speed-styles';
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
            
            #flashcard {
                transition: opacity 0.1s ease;
            }
            
            #knownBtn, #unknownBtn {
                transition: all 0.1s ease;
                user-select: none;
                -webkit-tap-highlight-color: transparent;
            }
            
            #knownBtn:active, #unknownBtn:active {
                transform: scale(0.95);
            }
        `;
        document.head.appendChild(style);
    }
}

console.log('📈 高速化統合版 main.js 読み込み完了');