console.log("🔧 カード表示修正版 main.js v2 が読み込まれました");

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

// ========== 事前レンダリングシステム（初期表示修正版） ==========
function prerenderAllCards() {
    console.log("🚀 全カード事前レンダリング開始（初期表示修正版）");
    
    const flashcard = document.getElementById('flashcard');
    if (!flashcard) return;
    
    // フラッシュカードを相対配置に
    flashcard.style.position = 'relative';
    flashcard.style.overflow = 'hidden';
    flashcard.innerHTML = '';
    
    // 画像読み込み状況をリセット
    imageLoadTracker = { totalImages: 0, loadedImages: 0, failedImages: 0, imageStatus: {} };
    
    // 全カードを事前に作成
    cards.forEach(function(card, index) {
        const cardElement = createCardElement(card, index);
        flashcard.appendChild(cardElement);
        prerenderedCards.push(cardElement);
        
        // 🔥 修正：最初のカードは表示、それ以外は非表示
        if (index === 0) {
            cardElement.style.display = 'flex';
            console.log(`🎯 カード1を初期表示に設定`);
        } else {
            cardElement.style.display = 'none';
        }
    });
    
    console.log("✅ 事前レンダリング完了: " + cards.length + "枚");
    console.log("📸 画像読み込み状況: 総数=" + imageLoadTracker.totalImages + ", 読み込み完了=" + imageLoadTracker.loadedImages + ", 失敗=" + imageLoadTracker.failedImages);
}

// ========== 修正版カード作成関数（画像番号修正） ==========
function createCardElement(card, index) {
    const container = document.createElement('div');
    container.className = 'prerendered-card';
    container.dataset.cardIndex = index;
    container.dataset.cardId = card.id;
    
    // 問題部分
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-container';
    problemDiv.dataset.section = 'problem';
    
    // 🔥 修正：カード番号を1から開始に変更
    const cardNumber = index + 1;
    
    // 問題画像の処理（カード番号修正版）
    if (card.image_problem) {
        const img = createImageElement(card.image_problem, '問題画像', cardNumber, 'problem');
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
    
    // 解答画像の処理（カード番号修正版）
    if (card.image_answer) {
        const answerImg = createImageElement(card.image_answer, '解答画像', cardNumber, 'answer');
        answerDiv.appendChild(answerImg);
        imageLoadTracker.totalImages++;
    }
    
    container.appendChild(problemDiv);
    container.appendChild(answerDiv);
    
    return container;
}

// ========== 画像要素作成関数（状況追跡強化） ==========
function createImageElement(src, alt, cardNumber, type) {
    const img = document.createElement('img');
    
    // 🔥 修正：画像IDを作成
    const imageId = `card${cardNumber}_${type}`;
    
    // 基本属性設定
    img.src = src;
    img.alt = alt;
    img.loading = 'eager';
    img.crossOrigin = 'anonymous';
    img.id = imageId;
    
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
    img.dataset.cardNumber = cardNumber;
    img.dataset.imageType = type;
    img.dataset.originalSrc = src;
    
    // 🔥 画像状況を初期化
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
        console.log(`📐 画像サイズ: ${this.naturalWidth}x${this.naturalHeight} → 表示サイズ: ${this.offsetWidth}x${this.offsetHeight}`);
        
        // 画像が見えているかチェック
        const isVisible = this.offsetParent !== null && this.offsetWidth > 0 && this.offsetHeight > 0;
        imageLoadTracker.imageStatus[imageId].visible = isVisible;
        console.log(`👁️ 画像表示状態: ${isVisible ? '表示中' : '非表示'}`);
        
        // 🔥 最初のカードの問題画像が読み込まれた場合は強制表示確認
        if (cardNumber === 1 && type === 'problem') {
            setTimeout(function() {
                forceShowFirstCard();
            }, 100);
        }
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

// ========== 最初のカード強制表示関数 ==========
function forceShowFirstCard() {
    console.log("🎯 最初のカード強制表示チェック");
    
    if (prerenderedCards[0]) {
        const firstCard = prerenderedCards[0];
        const problemDiv = firstCard.querySelector('.problem-container');
        const answerDiv = firstCard.querySelector('.answer-container');
        
        // カード自体を確実に表示
        firstCard.style.display = 'flex';
        firstCard.style.visibility = 'visible';
        firstCard.style.opacity = '1';
        
        if (problemDiv && answerDiv) {
            // 問題を確実に表示
            problemDiv.style.display = 'flex';
            problemDiv.style.visibility = 'visible';
            problemDiv.style.opacity = '1';
            
            // 解答を確実に非表示
            answerDiv.style.display = 'none';
            answerDiv.style.visibility = 'hidden';
            answerDiv.style.opacity = '0';
            
            // 問題画像の強制表示
            const problemImg = problemDiv.querySelector('img');
            if (problemImg) {
                problemImg.style.display = 'block';
                problemImg.style.visibility = 'visible';
                problemImg.style.opacity = '1';
                
                console.log(`🔍 最初のカード画像強制表示: ${problemImg.id}`);
                
                // 表示確認
                setTimeout(function() {
                    checkImageVisibility(problemImg, 1, 'problem');
                }, 50);
            }
        }
        
        console.log("✅ 最初のカード強制表示完了");
    }
}

// ========== 修正版カード切り替え（ログ強化） ==========
function switchToCardInstantly(newIndex) {
    if (newIndex >= cards.length) return false;
    
    console.log(`🔄 カード切り替え: ${currentIndex + 1} → ${newIndex + 1}`);
    
    // 現在のカードを完全に非表示
    if (prerenderedCards[currentIndex]) {
        prerenderedCards[currentIndex].style.display = 'none';
        console.log(`👻 カード${currentIndex + 1}を非表示に設定`);
    }
    
    // 新しいカードを表示
    if (prerenderedCards[newIndex]) {
        prerenderedCards[newIndex].style.display = 'flex';
        console.log(`👁️ カード${newIndex + 1}を表示に設定`);
        
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
                    checkImageVisibility(problemImg, newIndex + 1, 'problem');
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

// ========== 画像表示状況確認関数（詳細ログ強化） ==========
function checkImageVisibility(img, cardNumber, type) {
    const imageId = `card${cardNumber}_${type}`;
    const isVisible = img.offsetParent !== null && img.offsetWidth > 0 && img.offsetHeight > 0;
    const isLoaded = img.complete && img.naturalHeight !== 0;
    
    console.log(`🔍 画像表示確認: ${imageId}`);
    console.log(`  - 読み込み完了: ${isLoaded}`);
    console.log(`  - 表示状態: ${isVisible}`);
    console.log(`  - 要素サイズ: ${img.offsetWidth}x${img.offsetHeight}`);
    console.log(`  - 自然サイズ: ${img.naturalWidth}x${img.naturalHeight}`);
    console.log(`  - スタイル: display=${img.style.display}, visibility=${img.style.visibility}`);
    console.log(`  - 親要素表示: ${img.parentElement ? img.parentElement.style.display : 'unknown'}`);
    
    // 画像状況を更新
    if (imageLoadTracker.imageStatus[imageId]) {
        imageLoadTracker.imageStatus[imageId].visible = isVisible;
    }
    
    if (!isVisible && isLoaded) {
        console.warn(`⚠️ 画像は読み込まれているが表示されていません: ${imageId}`);
        
        // 親要素も含めて強制表示を試行
        const parentContainer = img.closest('.problem-container, .answer-container');
        const grandParentCard = img.closest('.prerendered-card');
        
        if (parentContainer) {
            parentContainer.style.display = 'flex';
            parentContainer.style.visibility = 'visible';
            parentContainer.style.opacity = '1';
            console.log(`🔧 親コンテナも強制表示: ${imageId}`);
        }
        
        if (grandParentCard) {
            grandParentCard.style.display = 'flex';
            grandParentCard.style.visibility = 'visible';
            grandParentCard.style.opacity = '1';
            console.log(`🔧 カード全体も強制表示: ${imageId}`);
        }
        
        // 画像自体も強制表示
        img.style.display = 'block !important';
        img.style.visibility = 'visible !important';
        img.style.opacity = '1 !important';
        
        setTimeout(function() {
            const stillNotVisible = img.offsetWidth === 0 || img.offsetHeight === 0;
            if (stillNotVisible) {
                console.error(`❌ 強制表示も失敗: ${imageId}`);
            } else {
                console.log(`✅ 強制表示成功: ${imageId}`);
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

// ========== 修正版解答切り替え（ログ強化） ==========
function toggleAnswerInstantly() {
    if (!prerenderedCards[currentIndex]) return;
    
    const problemDiv = prerenderedCards[currentIndex].querySelector('.problem-container');
    const answerDiv = prerenderedCards[currentIndex].querySelector('.answer-container');
    
    if (problemDiv && answerDiv) {
        showingAnswer = !showingAnswer;
        
        console.log(`🔄 解答切り替え: ${showingAnswer ? '問題→解答' : '解答→問題'} (カード${currentIndex + 1})`);
        
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
                    checkImageVisibility(answerImg, currentIndex + 1, 'answer');
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
                    checkImageVisibility(problemImg, currentIndex + 1, 'problem');
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

// ========== デバッグ機能（詳細ログ強化版） ==========
function debugStatus() {
    console.log("=== デバッグ情報（詳細ログ強化版） ===");
    console.log("カード数:", cards.length);
    console.log("現在のインデックス:", currentIndex);
    console.log("解答表示中:", showingAnswer);
    console.log("プリレンダリングカード数:", prerenderedCards.length);
    console.log("画像読み込み状況:", imageLoadTracker);
    
    // 各画像の詳細状況
    console.log("=== 画像詳細状況 ===");
    Object.keys(imageLoadTracker.imageStatus).forEach(function(imageId) {
        const status = imageLoadTracker.imageStatus[imageId];
        console.log(`${imageId}:`, status);
    });
    
    // 現在表示中のカードの詳細状態
    if (prerenderedCards[currentIndex]) {
        const currentCard = prerenderedCards[currentIndex];
        const problemDiv = currentCard.querySelector('.problem-container');
        const answerDiv = currentCard.querySelector('.answer-container');
        
        console.log("=== 現在のカード表示状態 ===");
        console.log("カード表示:", {
            card_display: currentCard.style.display,
            card_visibility: currentCard.style.visibility,
            card_opacity: currentCard.style.opacity
        });
        
        console.log("問題部分:", {
            problem_display: problemDiv ? problemDiv.style.display : "not found",
            problem_visibility: problemDiv ? problemDiv.style.visibility : "not found",
            problem_opacity: problemDiv ? problemDiv.style.opacity : "not found"
        });
        
        console.log("解答部分:", {
            answer_display: answerDiv ? answerDiv.style.display : "not found",
            answer_visibility: answerDiv ? answerDiv.style.visibility : "not found", 
            answer_opacity: answerDiv ? answerDiv.style.opacity : "not found"
        });
        
        // 画像要素の詳細確認
        const problemImg = problemDiv ? problemDiv.querySelector('img') : null;
        const answerImg = answerDiv ? answerDiv.querySelector('img') : null;
        
        if (problemImg) {
            console.log("問題画像詳細:", {
                id: problemImg.id,
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
                id: answerImg.id,
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

// ========== 画像修復関数（強化版） ==========
function fixAllImages() {
    console.log("🛠️ 全画像修復を実行（強化版）");
    
    const allImages = document.querySelectorAll('#flashcard img');
    let fixedCount = 0;
    
    allImages.forEach(function(img, index) {
        const isHidden = img.offsetWidth === 0 || img.offsetHeight === 0 || img.offsetParent === null;
        
        if (isHidden) {
            console.log(`🔧 画像${img.id || index}を修復中...`);
            
            // 画像自体の修復
            img.style.width = '100%';
            img.style.maxWidth = '100%';
            img.style.height = 'auto';
            img.style.display = 'block';
            img.style.visibility = 'visible';
            img.style.opacity = '1';
            
            // 親要素の修復
            const parentContainer = img.closest('.problem-container, .answer-container');
            const grandParentCard = img.closest('.prerendered-card');
            
            if (parentContainer && parentContainer.style.display === 'none') {
                console.log(`🔧 親コンテナも修復: ${img.id || index}`);
                parentContainer.style.display = 'flex';
                parentContainer.style.visibility = 'visible';
                parentContainer.style.opacity = '1';
            }
            
            if (grandParentCard && grandParentCard.style.display === 'none') {
                console.log(`🔧 カード全体も修復: ${img.id || index}`);
                grandParentCard.style.display = 'flex';
                grandParentCard.style.visibility = 'visible';
                grandParentCard.style.opacity = '1';
            }
            
            fixedCount++;
        }
    });
    
    console.log(`✅ 画像修復完了: ${fixedCount}個の画像を修復`);
    
    // 修復後の状態確認
    setTimeout(debugStatus, 500);
}

// ========== 初期化（強制表示強化版） ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔧 カード表示修正版初期化開始");
    
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
    
    // 🔥 修正：初期表示状態を段階的に設定
    setTimeout(function() {
        console.log("🎯 初期表示状態設定開始");
        forceShowFirstCard();
    }, 500);
    
    // さらに遅延してデバッグ情報を表示
    setTimeout(function() {
        console.log("📊 初期化完了後のデバッグ情報:");
        debugStatus();
    }, 1500);
    
    console.log("🔧 カード表示修正版初期化完了");
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
            case 'd':
                // デバッグ用：D キーでデバッグ情報表示
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
window.forceShowFirstCard = forceShowFirstCard;

console.log("🔧 カード表示修正版読み込み完了");