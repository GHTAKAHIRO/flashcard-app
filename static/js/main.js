console.log("🔧 画像表示修正版 main.js が読み込まれました");

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
    failedImages: 0
};

// ========== 事前レンダリングシステム（画像読み込み強化版） ==========
function prerenderAllCards() {
    console.log("🚀 全カード事前レンダリング開始（画像読み込み強化版）");
    
    const flashcard = document.getElementById('flashcard');
    if (!flashcard) return;
    
    // フラッシュカードを相対配置に
    flashcard.style.position = 'relative';
    flashcard.style.overflow = 'hidden';
    flashcard.innerHTML = '';
    
    // 画像読み込み状況をリセット
    imageLoadTracker = { totalImages: 0, loadedImages: 0, failedImages: 0 };
    
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
    console.log("📸 画像読み込み状況: 総数=" + imageLoadTracker.totalImages + ", 読み込み完了=" + imageLoadTracker.loadedImages + ", 失敗=" + imageLoadTracker.failedImages);
}

// ========== 修正版カード作成関数（画像読み込み強化） ==========
function createCardElement(card, index) {
    const container = document.createElement('div');
    container.className = 'prerendered-card';
    container.dataset.cardIndex = index;
    container.dataset.cardId = card.id;
    
    // 問題部分
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-container';
    problemDiv.dataset.section = 'problem';
    
    // 問題画像の処理（改良版）
    if (card.image_problem) {
        const img = createImageElement(card.image_problem, '問題画像', index, 'problem');
        problemDiv.appendChild(img);
        imageLoadTracker.totalImages++;
    }
    
    // 問題テキストの処理
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = card.problem_number + ": " + card.topic;
        text.style.margin = '10px';
        text.style.padding = '10px';
        text.style.fontSize = '16px';
        text.style.fontWeight = 'bold';
        text.style.color = '#333';
        text.style.backgroundColor = 'rgba(255,255,255,0.9)';
        text.style.borderRadius = '4px';
        text.style.wordWrap = 'break-word';
        problemDiv.appendChild(text);
    }
    
    // 解答部分（必ず非表示で開始）
    const answerDiv = document.createElement('div');
    answerDiv.className = 'answer-container';
    answerDiv.dataset.section = 'answer';
    answerDiv.style.display = 'none';
    answerDiv.style.visibility = 'hidden';
    answerDiv.style.opacity = '0';
    
    // 解答画像の処理（改良版）
    if (card.image_answer) {
        const answerImg = createImageElement(card.image_answer, '解答画像', index, 'answer');
        answerDiv.appendChild(answerImg);
        imageLoadTracker.totalImages++;
    }
    
    container.appendChild(problemDiv);
    container.appendChild(answerDiv);
    
    return container;
}

// ========== 画像要素作成関数（エラーハンドリング強化） ==========
function createImageElement(src, alt, cardIndex, type) {
    const img = document.createElement('img');
    
    // 基本属性設定
    img.src = src;
    img.alt = alt;
    img.loading = 'eager';
    img.crossOrigin = 'anonymous'; // CORS対応
    
    // 強化されたスタイル設定
    img.style.width = '100%';
    img.style.maxWidth = '100%';
    img.style.height = 'auto';
    img.style.objectFit = 'contain';
    img.style.display = 'block';
    img.style.margin = '0 auto';
    img.style.border = 'none';
    img.style.boxShadow = 'none';
    img.style.borderRadius = '0';
    
    // データ属性
    img.dataset.cardIndex = cardIndex;
    img.dataset.imageType = type;
    img.dataset.originalSrc = src;
    
    // 読み込み成功イベント
    img.onload = function() {
        imageLoadTracker.loadedImages++;
        console.log(`✅ 画像読み込み成功: カード${cardIndex + 1} ${type} (${imageLoadTracker.loadedImages}/${imageLoadTracker.totalImages})`);
        
        // 画像サイズ情報をログ出力
        console.log(`📐 画像サイズ: ${this.naturalWidth}x${this.naturalHeight} → 表示サイズ: ${this.offsetWidth}x${this.offsetHeight}`);
        
        // 画像が見えているかチェック
        const isVisible = this.offsetParent !== null && this.offsetWidth > 0 && this.offsetHeight > 0;
        console.log(`👁️ 画像表示状態: ${isVisible ? '表示中' : '非表示'}`);
    };
    
    // 読み込み失敗イベント
    img.onerror = function() {
        imageLoadTracker.failedImages++;
        console.error(`❌ 画像読み込み失敗: カード${cardIndex + 1} ${type} - ${src}`);
        
        // エラー時の代替表示
        this.style.backgroundColor = '#f8f9fa';
        this.style.border = '2px dashed #dee2e6';
        this.style.minHeight = '200px';
        this.style.display = 'flex';
        this.style.alignItems = 'center';
        this.style.justifyContent = 'center';
        
        // エラーメッセージを表示
        const errorDiv = document.createElement('div');
        errorDiv.textContent = `画像読み込みエラー: ${alt}`;
        errorDiv.style.textAlign = 'center';
        errorDiv.style.color = '#6c757d';
        errorDiv.style.fontSize = '14px';
        this.parentNode.appendChild(errorDiv);
    };
    
    return img;
}

// ========== 修正版カード切り替え（画像表示確認強化） ==========
function switchToCardInstantly(newIndex) {
    if (newIndex >= cards.length) return false;
    
    // 現在のカードを完全に非表示
    if (prerenderedCards[currentIndex]) {
        prerenderedCards[currentIndex].style.display = 'none';
    }
    
    // 新しいカードを表示
    if (prerenderedCards[newIndex]) {
        prerenderedCards[newIndex].style.display = 'flex';
        
        // 問題・解答の表示状態を強制リセット
        const problemDiv = prerenderedCards[newIndex].querySelector('.problem-container');
        const answerDiv = prerenderedCards[newIndex].querySelector('.answer-container');
        
        if (problemDiv && answerDiv) {
            // 問題を確実に表示
            problemDiv.style.display = 'flex';
            problemDiv.style.visibility = 'visible';
            problemDiv.style.opacity = '1';
            
            // 解答を確実に非表示
            answerDiv.style.display = 'none';
            answerDiv.style.visibility = 'hidden';
            answerDiv.style.opacity = '0';
            
            // 画像の強制表示確認
            const problemImg = problemDiv.querySelector('img');
            if (problemImg) {
                problemImg.style.display = 'block';
                problemImg.style.visibility = 'visible';
                problemImg.style.opacity = '1';
                
                // 画像読み込み状況を確認
                setTimeout(function() {
                    checkImageVisibility(problemImg, newIndex, 'problem');
                }, 100);
            }
            
            console.log(`📝 カード${newIndex + 1}: 問題表示、解答非表示に設定`);
        }
    }
    
    currentIndex = newIndex;
    showingAnswer = false;
    
    // 進捗更新
    updateProgressInstantly();
    
    return true;
}

// ========== 画像表示状況確認関数 ==========
function checkImageVisibility(img, cardIndex, type) {
    const isVisible = img.offsetParent !== null && img.offsetWidth > 0 && img.offsetHeight > 0;
    const isLoaded = img.complete && img.naturalHeight !== 0;
    
    console.log(`🔍 画像表示確認: カード${cardIndex + 1} ${type}`);
    console.log(`  - 読み込み完了: ${isLoaded}`);
    console.log(`  - 表示状態: ${isVisible}`);
    console.log(`  - 要素サイズ: ${img.offsetWidth}x${img.offsetHeight}`);
    console.log(`  - 自然サイズ: ${img.naturalWidth}x${img.naturalHeight}`);
    console.log(`  - スタイル: display=${img.style.display}, visibility=${img.style.visibility}`);
    
    if (!isVisible && isLoaded) {
        console.warn(`⚠️ 画像は読み込まれているが表示されていません`);
        
        // 強制表示を試行
        img.style.display = 'block !important';
        img.style.visibility = 'visible !important';
        img.style.opacity = '1 !important';
        
        setTimeout(function() {
            const stillNotVisible = img.offsetWidth === 0 || img.offsetHeight === 0;
            if (stillNotVisible) {
                console.error(`❌ 強制表示も失敗: カード${cardIndex + 1} ${type}`);
            } else {
                console.log(`✅ 強制表示成功: カード${cardIndex + 1} ${type}`);
            }
        }, 50);
    }
}

function updateProgressInstantly() {
    const progressElement = document.getElementById('progress-info');
    if (progressElement) {
        progressElement.innerHTML = '<i class="fas fa-chart-line"></i> ' + (currentIndex + 1) + ' / ' + cards.length;
    }
}

// ========== 修正版解答切り替え（画像表示確認強化） ==========
function toggleAnswerInstantly() {
    if (!prerenderedCards[currentIndex]) return;
    
    const problemDiv = prerenderedCards[currentIndex].querySelector('.problem-container');
    const answerDiv = prerenderedCards[currentIndex].querySelector('.answer-container');
    
    if (problemDiv && answerDiv) {
        showingAnswer = !showingAnswer;
        
        if (showingAnswer) {
            // 解答を表示、問題を非表示
            problemDiv.style.display = 'none';
            problemDiv.style.visibility = 'hidden';
            problemDiv.style.opacity = '0';
            
            answerDiv.style.display = 'flex';
            answerDiv.style.visibility = 'visible';
            answerDiv.style.opacity = '1';
            
            // 解答画像の強制表示確認
            const answerImg = answerDiv.querySelector('img');
            if (answerImg) {
                answerImg.style.display = 'block';
                answerImg.style.visibility = 'visible';
                answerImg.style.opacity = '1';
                
                setTimeout(function() {
                    checkImageVisibility(answerImg, currentIndex, 'answer');
                }, 100);
            }
            
            console.log("👁️ 解答表示モード");
        } else {
            // 問題を表示、解答を非表示
            problemDiv.style.display = 'flex';
            problemDiv.style.visibility = 'visible';
            problemDiv.style.opacity = '1';
            
            answerDiv.style.display = 'none';
            answerDiv.style.visibility = 'hidden';
            answerDiv.style.opacity = '0';
            
            // 問題画像の強制表示確認
            const problemImg = problemDiv.querySelector('img');
            if (problemImg) {
                problemImg.style.display = 'block';
                problemImg.style.visibility = 'visible';
                problemImg.style.opacity = '1';
                
                setTimeout(function() {
                    checkImageVisibility(problemImg, currentIndex, 'problem');
                }, 100);
            }
            
            console.log("📝 問題表示モード");
        }
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

// ========== 完了処理（簡略版） ==========
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

// ========== デバッグ機能（画像表示強化版） ==========
function debugStatus() {
    console.log("=== デバッグ情報（画像表示強化版） ===");
    console.log("カード数:", cards.length);
    console.log("現在のインデックス:", currentIndex);
    console.log("解答表示中:", showingAnswer);
    console.log("プリレンダリングカード数:", prerenderedCards.length);
    console.log("画像読み込み状況:", imageLoadTracker);
    
    // 現在表示中のカードの詳細状態
    if (prerenderedCards[currentIndex]) {
        const currentCard = prerenderedCards[currentIndex];
        const problemDiv = currentCard.querySelector('.problem-container');
        const answerDiv = currentCard.querySelector('.answer-container');
        
        console.log("現在のカード表示状態:", {
            card_display: currentCard.style.display,
            problem_display: problemDiv ? problemDiv.style.display : "not found",
            problem_visibility: problemDiv ? problemDiv.style.visibility : "not found",
            answer_display: answerDiv ? answerDiv.style.display : "not found",
            answer_visibility: answerDiv ? answerDiv.style.visibility : "not found",
            showingAnswer_flag: showingAnswer
        });
        
        // 画像要素の詳細確認
        const problemImg = problemDiv ? problemDiv.querySelector('img') : null;
        const answerImg = answerDiv ? answerDiv.querySelector('img') : null;
        
        if (problemImg) {
            console.log("問題画像詳細:", {
                src: problemImg.src,
                complete: problemImg.complete,
                naturalWidth: problemImg.naturalWidth,
                naturalHeight: problemImg.naturalHeight,
                offsetWidth: problemImg.offsetWidth,
                offsetHeight: problemImg.offsetHeight,
                visible: problemImg.offsetParent !== null,
                display: problemImg.style.display,
                visibility: problemImg.style.visibility,
                opacity: problemImg.style.opacity
            });
        } else {
            console.log("問題画像: なし");
        }
        
        if (answerImg) {
            console.log("解答画像詳細:", {
                src: answerImg.src,
                complete: answerImg.complete,
                naturalWidth: answerImg.naturalWidth,
                naturalHeight: answerImg.naturalHeight,
                offsetWidth: answerImg.offsetWidth,
                offsetHeight: answerImg.offsetHeight,
                visible: answerImg.offsetParent !== null,
                display: answerImg.style.display,
                visibility: answerImg.style.visibility,
                opacity: answerImg.style.opacity
            });
        } else {
            console.log("解答画像: なし");
        }
    }
}

// ========== 画像修復関数 ==========
function fixAllImages() {
    console.log("🛠️ 全画像修復を実行");
    
    const allImages = document.querySelectorAll('#flashcard img');
    let fixedCount = 0;
    
    allImages.forEach(function(img, index) {
        if (img.offsetWidth === 0 || img.offsetHeight === 0) {
            console.log(`🔧 画像${index}を修復中...`);
            
            img.style.width = '100%';
            img.style.maxWidth = '100%';
            img.style.height = 'auto';
            img.style.display = 'block';
            img.style.visibility = 'visible';
            img.style.opacity = '1';
            
            fixedCount++;
        }
    });
    
    console.log(`✅ 画像修復完了: ${fixedCount}個の画像を修復`);
    
    // 修復後の状態確認
    setTimeout(debugStatus, 500);
}

// ========== 初期化（画像表示強化版） ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔧 画像表示修正版初期化開始");
    
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません");
        return;
    }
    
    cards = shuffle(rawCards.slice());
    currentIndex = 0;
    showingAnswer = false;
    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    
    console.log("📊 カードデータ: " + cards.length + "枚");
    console.log("📚 練習モード: " + isPracticeMode);
    
    prerenderAllCards();
    setupInstantEvents();
    setupInstantKeyboard();
    
    // 初期表示状態を確実に設定（画像表示強化）
    setTimeout(function() {
        if (prerenderedCards[0]) {
            const problemDiv = prerenderedCards[0].querySelector('.problem-container');
            const answerDiv = prerenderedCards[0].querySelector('.answer-container');
            
            if (problemDiv && answerDiv) {
                problemDiv.style.display = 'flex';
                problemDiv.style.visibility = 'visible';
                problemDiv.style.opacity = '1';
                
                answerDiv.style.display = 'none';
                answerDiv.style.visibility = 'hidden';
                answerDiv.style.opacity = '0';
                
                // 初期画像の表示確認
                const problemImg = problemDiv.querySelector('img');
                if (problemImg) {
                    checkImageVisibility(problemImg, 0, 'problem');
                }
                
                console.log("🎯 初期表示状態確認完了: 問題表示、解答非表示");
            }
        }
        
        // デバッグ情報を表示
        debugStatus();
    }, 1000);
    
    console.log("🔧 画像表示修正版初期化完了");
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
                // デバッグ用：R キーで画像修復
                e.preventDefault();
                fixAllImages();
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

console.log("🔧 画像表示修正版読み込み完了");