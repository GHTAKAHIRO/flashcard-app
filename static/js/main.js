console.log("🔧 デバッグ修正版 main.js が読み込まれました");

// ========== デバッグ情報出力 ==========
function debugCurrentState() {
    console.log("=== デバッグ情報 ===");
    console.log("rawCards:", typeof rawCards !== 'undefined' ? rawCards.length : 'undefined');
    console.log("mode:", typeof mode !== 'undefined' ? mode : 'undefined');
    console.log("stage:", typeof stage !== 'undefined' ? stage : 'undefined');
    
    console.log("DOM要素チェック:");
    console.log("- flashcard:", document.getElementById('flashcard'));
    console.log("- knownBtn:", document.getElementById('knownBtn'));
    console.log("- unknownBtn:", document.getElementById('unknownBtn'));
    console.log("- correct-count:", document.getElementById('correct-count'));
    console.log("- incorrect-count:", document.getElementById('incorrect-count'));
    console.log("==================");
}

// ========== 安全な初期化システム ==========
let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};
let isPracticeMode = false;

// DOM要素の安全な取得
function safeGetElement(id) {
    const element = document.getElementById(id);
    if (!element) {
        console.warn(`⚠️ 要素が見つかりません: ${id}`);
    }
    return element;
}

// 安全なイベントリスナー追加
function safeAddEventListener(elementId, event, handler) {
    const element = safeGetElement(elementId);
    if (element) {
        element.addEventListener(event, handler);
        console.log(`✅ イベントリスナー追加成功: ${elementId}`);
    } else {
        console.error(`❌ イベントリスナー追加失敗: ${elementId}`);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    console.log("🚀 DOM読み込み完了");
    
    // デバッグ情報出力
    debugCurrentState();
    
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません！");
        return;
    }

    console.log(`📊 カードデータ: ${rawCards.length}枚`);

    // 基本的なイベントリスナー設定
    safeAddEventListener('flashcard', 'click', toggleAnswer);
    safeAddEventListener('knownBtn', 'click', markKnown);
    safeAddEventListener('unknownBtn', 'click', markUnknown);

    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    console.log("📚 練習モード:", isPracticeMode);
    
    initCards(rawCards);
    setupKeyboard();
    
    console.log('✅ 初期化完了');
});

function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

function initCards(data) {
    console.log("🔄 カード初期化開始");
    
    cards = shuffle(data.slice());
    currentIndex = 0;
    showingAnswer = false;
    cardStatus = {};
    
    console.log(`📝 シャッフル完了: ${cards.length}枚`);
    
    renderCard();
}

// シンプルなカードレンダリング
function renderCard() {
    console.log(`🎴 カードレンダリング: ${currentIndex + 1}/${cards.length}`);
    
    const card = cards[currentIndex];
    const cardDiv = safeGetElement('flashcard');
    
    if (!cardDiv) {
        console.error("❌ flashcard要素が見つかりません");
        return;
    }
    
    if (!card) {
        console.error("❌ カードデータがありません");
        return;
    }
    
    console.log("📄 表示カード:", card);
    
    // DOM更新
    cardDiv.innerHTML = '';

    const questionDiv = document.createElement('div');
    questionDiv.id = 'problem-container';
    
    if (card.image_problem) {
        console.log("🖼️ 問題画像:", card.image_problem);
        const img = document.createElement('img');
        img.src = card.image_problem;
        img.style.cssText = 'max-width: 100%; height: auto; display: block; margin: 0 auto;';
        img.alt = '問題画像';
        
        img.onload = () => console.log("✅ 問題画像読み込み完了");
        img.onerror = () => console.error("❌ 問題画像読み込み失敗");
        
        questionDiv.appendChild(img);
    }
    
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = `${card.problem_number}: ${card.topic}`;
        text.style.cssText = 'margin: 10px 0; font-weight: bold; text-align: center;';
        questionDiv.appendChild(text);
    }

    cardDiv.appendChild(questionDiv);

    // 解答部分も準備
    if (card.image_answer) {
        const answerDiv = document.createElement('div');
        answerDiv.id = 'answer-container';
        answerDiv.style.display = showingAnswer ? 'block' : 'none';
        
        const answerImg = document.createElement('img');
        answerImg.src = card.image_answer;
        answerImg.style.cssText = 'max-width: 100%; height: auto; display: block; margin: 0 auto;';
        answerImg.alt = '解答画像';
        answerDiv.appendChild(answerImg);
        
        cardDiv.appendChild(answerDiv);
    }
    
    // 進捗更新
    updateProgress();
    
    console.log("✅ カードレンダリング完了");
}

function toggleAnswer() {
    console.log("🔄 解答切り替え");
    
    showingAnswer = !showingAnswer;
    
    const problemContainer = safeGetElement('problem-container');
    const answerContainer = safeGetElement('answer-container');
    
    if (problemContainer && answerContainer) {
        if (showingAnswer) {
            problemContainer.style.display = 'none';
            answerContainer.style.display = 'block';
            console.log("👁️ 解答表示");
        } else {
            problemContainer.style.display = 'block';
            answerContainer.style.display = 'none';
            console.log("❓ 問題表示");
        }
    } else {
        console.error("❌ 解答切り替え要素が見つかりません");
    }
}

function markKnown() {
    console.log("✅ 〇ボタンクリック");
    handleAnswer('known');
}

function markUnknown() {
    console.log("❌ ×ボタンクリック");
    handleAnswer('unknown');
}

function handleAnswer(result) {
    console.log(`📝 回答処理: ${result}`);
    
    const id = cards[currentIndex].id;
    cardStatus[id] = result;
    
    // カウンター更新
    updateCounters(result);
    
    // ボタンフィードバック
    const button = result === 'known' ? safeGetElement('knownBtn') : safeGetElement('unknownBtn');
    if (button) {
        button.style.transform = 'scale(0.95)';
        button.style.backgroundColor = result === 'known' ? '#45a049' : '#da190b';
        
        setTimeout(() => {
            button.style.transform = 'scale(1)';
            button.style.backgroundColor = '';
        }, 150);
    }
    
    // サーバーに送信
    sendResult(id, result);
}

function updateCounters(result) {
    const correctSpan = safeGetElement('correct-count');
    const incorrectSpan = safeGetElement('incorrect-count');
    
    if (result === 'known' && correctSpan) {
        const current = parseInt(correctSpan.textContent) || 0;
        correctSpan.textContent = current + 1;
        console.log(`✅ 正解カウンター: ${current + 1}`);
    } else if (result === 'unknown' && incorrectSpan) {
        const current = parseInt(incorrectSpan.textContent) || 0;
        incorrectSpan.textContent = current + 1;
        console.log(`❌ 不正解カウンター: ${current + 1}`);
    }
}

function updateProgress() {
    const progressElement = safeGetElement('progress-info');
    if (progressElement) {
        progressElement.innerHTML = `<i class="fas fa-chart-line"></i> ${currentIndex + 1} / ${cards.length}`;
    }
}

// サーバー送信（既存の関数）
async function sendResult(cardId, result) {
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
            // 完了判定
            if (data.chunk_test_completed || data.stage_test_completed) {
                console.log('[SUBMIT] テスト完了:', data);
                
                if (data.redirect_to_prepare) {
                    console.log('[SUBMIT] prepare画面に戻ります');
                    showMessage(data.message);
                    setTimeout(() => {
                        const currentSource = getCurrentSource();
                        window.location.href = `/prepare/${currentSource}`;
                    }, 2000);
                    return;
                }
            }
            
            if (data.practice_completed) {
                console.log('[SUBMIT] 練習完了:', data);
                
                if (data.redirect_to_prepare) {
                    console.log('[SUBMIT] prepare画面に戻ります');
                    showMessage(data.message);
                    setTimeout(() => {
                        const currentSource = getCurrentSource();
                        window.location.href = `/prepare/${currentSource}`;
                    }, 2000);
                    return;
                }
            }
            
            if (data.practice_continuing) {
                console.log('[SUBMIT] 練習継続:', data.remaining_count, '問残り');
                showMessage(data.message);
                
                setTimeout(() => {
                    nextCard();
                }, 1000);
                return;
            }
            
            // 通常の次の問題へ
            console.log('[SUBMIT] 通常の次問題へ');
            nextCard();
            
        } else {
            throw new Error(data.message || '回答の送信に失敗しました');
        }

    } catch (error) {
        console.error('[SUBMIT] エラー:', error);
        showMessage("❌ サーバーへの記録に失敗しました", "error");
        nextCard(); // エラーでも次に進む
    }
}

function nextCard() {
    console.log("➡️ 次のカードへ");
    
    currentIndex++;

    if (currentIndex >= cards.length) {
        console.log('[NEXTCARD] カード終了:', currentIndex, '/', cards.length);
        
        if (isPracticeMode) {
            console.log('[NEXTCARD] 練習モード - サーバーから新しいカードを待機');
            showMessage("問題を読み込んでいます...");
            
            setTimeout(() => {
                window.location.reload();
            }, 1000);
            return;
        } else {
            console.log('[NEXTCARD] テストモード完了 - prepare画面に戻る');
            showMessage("✅ テスト完了！");
            setTimeout(() => {
                const currentSource = getCurrentSource();
                window.location.href = `/prepare/${currentSource}`;
            }, 2000);
            return;
        }
    }

    showingAnswer = false;
    renderCard();
}

function showMessage(message, type = "info") {
    console.log('[MESSAGE]', type, ':', message);
    
    const existingMessage = document.getElementById('messageAlert');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.id = 'messageAlert';
    messageDiv.textContent = message;
    messageDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? '#f44336' : '#4CAF50'};
        color: white;
        padding: 12px 20px;
        border-radius: 6px;
        font-weight: bold;
        z-index: 1000;
        transform: translateX(100%);
        transition: transform 0.3s ease;
    `;
    
    document.body.appendChild(messageDiv);
    
    setTimeout(() => {
        messageDiv.style.transform = 'translateX(0)';
    }, 100);
    
    setTimeout(() => {
        messageDiv.style.transform = 'translateX(100%)';
        setTimeout(() => messageDiv.remove(), 300);
    }, 3000);
}

function getCurrentSource() {
    const pathParts = window.location.pathname.split('/');
    const source = pathParts[pathParts.length - 1];
    console.log('[SOURCE] 現在の教材:', source);
    return source;
}

// キーボードショートカット
function setupKeyboard() {
    console.log("⌨️ キーボードショートカット設定");
    
    document.addEventListener('keydown', (e) => {
        switch(e.key.toLowerCase()) {
            case 'j':
            case 'arrowleft':
                e.preventDefault();
                markKnown();
                break;
            case 'f':
            case 'arrowright':
                e.preventDefault();
                markUnknown();
                break;
            case ' ':
                e.preventDefault();
                toggleAnswer();
                break;
        }
    });
}

console.log('📈 デバッグ修正版 main.js 読み込み完了');