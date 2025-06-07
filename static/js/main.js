console.log("🔧 表示制御修正版 main.js v3 が読み込まれました");

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

// ========== 事前レンダリングシステム ==========
function prerenderAllCards() {
    console.log("🚀 全カード事前レンダリング開始（表示制御修正版）");
    
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
        
        // 最初のカードのみ表示
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

// ========== 修正版カード作成関数（表示制御強化） ==========
function createCardElement(card, index) {
    const container = document.createElement('div');
    container.className = 'prerendered-card';
    container.dataset.cardIndex = index;
    container.dataset.cardId = card.id;
    
    const cardNumber = index + 1;
    
    // 問題部分（初期状態：表示）
    const problemDiv = document.createElement('div');
    problemDiv.className = 'problem-container';
    problemDiv.dataset.section = 'problem';
    problemDiv.dataset.cardNumber = cardNumber;
    
    // 🔥 重要：問題部分の初期表示設定
    if (index === 0) {
        // 最初のカードの問題は表示
        problemDiv.style.display = 'flex';
        problemDiv.style.visibility = 'visible';
        problemDiv.style.opacity = '1';
    } else {
        // 他のカードの問題は非表示
        problemDiv.style.display = 'none';
        problemDiv.style.visibility = 'hidden';
        problemDiv.style.opacity = '0';
    }
    
    // 問題画像の処理
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
    
    // 解答部分（初期状態：必ず非表示）
    const answerDiv = document.createElement('div');
    answerDiv.className = 'answer-container';
    answerDiv.dataset.section = 'answer';
    answerDiv.dataset.cardNumber = cardNumber;
    
    // 🔥 重要：解答部分は常に非表示で初期化
    answerDiv.style.display = 'none';
    answerDiv.style.visibility = 'hidden';
    answerDiv.style.opacity = '0';
    
    // 解答画像の処理
    if (card.image_answer) {
        const answerImg = createImageElement(card.image_answer, '解答画像', cardNumber, 'answer');
        answerDiv.appendChild(answerImg);
        imageLoadTracker.totalImages++;
    }
    
    container.appendChild(problemDiv);
    container.appendChild(answerDiv);
    
    return container;
}

// ========== 画像要素作成関数（サイズ制御強化） ==========
function createImageElement(src, alt, cardNumber, type) {
    const img = document.createElement('img');
    
    const imageId = `card${cardNumber}_${type}`;
    
    // 基本属性設定
    img.src = src;
    img.alt = alt;
    img.loading = 'eager';
    img.crossOrigin = 'anonymous';
    img.id = imageId;
    
    // 🔥 サイズ制御強化：最大サイズ設定
    img.style.width = '100%';
    img.style.maxWidth = '100%';
    img.style.height = 'auto';
    img.style.maxHeight = '80vh'; // 画面高さの80%まで
    img.style.objectFit = 'contain';
    img.style.objectPosition = 'center';
    img.style.display = 'block';
    img.style.margin = '0 auto';
    img.style.border = 'none';
    img.style.boxShadow = 'none';
    img.style.borderRadius = '0';
    
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
        console.log(`📐 画像サイズ: ${this.naturalWidth}x${this.naturalHeight} → 表示サイズ: ${this.offsetWidth}x${this.offsetHeight}`);
        
        // 画像が見えているかチェック
        const isVisible = this.offsetParent !== null && this.offsetWidth > 0 && this.offsetHeight > 0;
        imageLoadTracker.imageStatus[imageId].visible = isVisible;
        console.log(`👁️ 画像表示状態: ${isVisible ? '表示中' : '非表示'}`);
        
        // 最初のカードの問題画像が読み込まれた場合は強制表示確認
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
            // 🔥 重要：問題を確実に表示
            problemDiv.style.display = 'flex';
            problemDiv.style.visibility = 'visible';
            problemDiv.style.opacity = '1';
            
            // 🔥 重要：解答を確実に非表示
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
                
                setTimeout(function() {
                    checkImageVisibility(problemImg, 1, 'problem');
                }, 50);
            }
        }
        
        // グローバル状態を確実に設定
        currentIndex = 0;
        showingAnswer = false;
        
        console.log("✅ 最初のカード強制表示完了");
    }
}

// ========== 修正版カード切り替え ==========
function switchToCardInstantly(newIndex) {
    if (newIndex >= cards.length) return false;
    
    console.log(`🔄 カード切り替え: ${currentIndex + 1} → ${newIndex + 1}`);
    
    // 現在のカードを完全に非表示
    if (prerenderedCards[currentIndex]) {
        const oldCard = prerenderedCards[currentIndex];
        oldCard.style.display = 'none';
        
        // 🔥 追加：現在のカードの全要素を確実に非表示
        const oldProblemDiv = oldCard.querySelector('.problem-container');
        const oldAnswerDiv = oldCard.querySelector('.answer-container');
        if (oldProblemDiv) {
            oldProblemDiv.style.display = 'none';
            oldProblemDiv.style.visibility = 'hidden';
            oldProblemDiv.style.opacity = '0';
        }
        if (oldAnswerDiv) {
            oldAnswerDiv.style.display = 'none';
            oldAnswerDiv.style.visibility = 'hidden';
            oldAnswerDiv.style.opacity = '0';
        }
        
        console.log(`👻 カード${currentIndex + 1}を完全非表示に設定`);
    }
    
    // 新しいカードを表示
    if (prerenderedCards[newIndex]) {
        const newCard = prerenderedCards[newIndex];
        newCard.style.display = 'flex';
        newCard.style.visibility = 'visible';
        newCard.style.opacity = '1';
        
        console.log(`👁️ カード${newIndex + 1}を表示に設定`);
        
        // 問題・解答の表示状態を強制リセット
        const problemDiv = newCard.querySelector('.problem-container');
        const answerDiv = newCard.querySelector('.answer-container');
        
        if (problemDiv && answerDiv) {
            // 🔥 重要：問題を確実に表示
            problemDiv.style.display = 'flex';
            problemDiv.style.visibility = 'visible';
            problemDiv.style.opacity = '1';
            
            // 🔥 重要：解答を確実に非表示
            answerDiv.style.display = 'none';
            answerDiv.style.visibility = 'hidden';
            answerDiv.style.opacity = '0';
            
            // 画像の強制表示確認
            const problemImg = problemDiv.querySelector('img');
            if (problemImg) {
                problemImg.style.display = 'block';
                problemImg.style.visibility = 'visible';
                problemImg.style.opacity = '1';
                
                setTimeout(function() {
                    checkImageVisibility(problemImg, newIndex + 1, 'problem');
                }, 100);
            }
            
            console.log(`📝 カード${newIndex + 1}: 問題表示、解答非表示に設定`);
        }
    }
    
    currentIndex = newIndex;
    showingAnswer = false; // 🔥 重要：フラグを確実にリセット
    
    updateProgressInstantly();
    
    return true;
}

// ========== 修正版解答切り替え（完全分離制御） ==========
function toggleAnswerInstantly() {
    if (!prerenderedCards[currentIndex]) return;
    
    const currentCard = prerenderedCards[currentIndex];
    const problemDiv = currentCard.querySelector('.problem-container');
    const answerDiv = currentCard.querySelector('.answer-container');
    
    if (problemDiv && answerDiv) {
        showingAnswer = !showingAnswer;
        
        console.log(`🔄 解答切り替え: ${showingAnswer ? '問題→解答' : '解答→問題'} (カード${currentIndex + 1})`);
        
        if (showingAnswer) {
            // 🔥 解答表示：問題を完全非表示、解答を完全表示
            
            // 問題部分を完全非表示
            problemDiv.style.display = 'none';
            problemDiv.style.visibility = 'hidden';
            problemDiv.style.opacity = '0';
            
            // 問題画像も確実に非表示
            const problemImg = problemDiv.querySelector('img');
            if (problemImg) {
                problemImg.style.display = 'none';
                problemImg.style.visibility = 'hidden';
                problemImg.style.opacity = '0';
            }
            
            // 解答部分を完全表示
            answerDiv.style.display = 'flex';
            answerDiv.style.visibility = 'visible';
            answerDiv.style.opacity = '1';
            
            // 解答画像を確実に表示
            const answerImg = answerDiv.querySelector('img');
            if (answerImg) {
                answerImg.style.display = 'block';
                answerImg.style.visibility = 'visible';
                answerImg.style.opacity = '1';
                
                setTimeout(function() {
                    checkImageVisibility(answerImg, currentIndex + 1, 'answer');
                }, 100);
            }
            
            console.log("👁️ 解答表示モード：問題完全非表示、解答完全表示");
        } else {
            // 🔥 問題表示：解答を完全非表示、問題を完全表示
            
            // 解答部分を完全非表示
            answerDiv.style.display = 'none';
            answerDiv.style.visibility = 'hidden';
            answerDiv.style.opacity = '0';
            
            // 解答画像も確実に非表示
            const answerImg = answerDiv.querySelector('img');
            if (answerImg) {
                answerImg.style.display = 'none';
                answerImg.style.visibility = 'hidden';
                answerImg.style.opacity = '0';
            }
            
            // 問題部分を完全表示
            problemDiv.style.display = 'flex';
            problemDiv.style.visibility = 'visible';
            problemDiv.style.opacity = '1';
            
            // 問題画像を確実に表示
            const problemImg = problemDiv.querySelector('img');
            if (problemImg) {
                problemImg.style.display = 'block';
                problemImg.style.visibility = 'visible';
                problemImg.style.opacity = '1';
                
                setTimeout(function() {
                    checkImageVisibility(problemImg, currentIndex + 1, 'problem');
                }, 100);
            }
            
            console.log("📝 問題表示モード：解答完全非表示、問題完全表示");
        }
    }
}

// ========== 画像表示状況確認関数（検証強化版） ==========
function checkImageVisibility(img, cardNumber, type) {
    const imageId = `card${cardNumber}_${type}`;
    const isVisible = img.offsetParent !== null && img.offsetWidth > 0 && img.offsetHeight > 0;
    const isLoaded = img.complete && img.naturalHeight !== 0;
    
    // 親要素の表示状況も確認
    const parentContainer = img.closest('.problem-container, .answer-container');
    const grandParentCard = img.closest('.prerendered-card');
    
    const parentVisible = parentContainer ? parentContainer.offsetParent !== null : false;
    const cardVisible = grandParentCard ? grandParentCard.offsetParent !== null : false;
    
    console.log(`🔍 画像表示確認: ${imageId}`);
    console.log(`  - 読み込み完了: ${isLoaded}`);
    console.log(`  - 画像表示状態: ${isVisible}`);
    console.log(`  - 親コンテナ表示: ${parentVisible}`);
    console.log(`  - カード表示: ${cardVisible}`);
    console.log(`  - 要素サイズ: ${img.offsetWidth}x${img.offsetHeight}`);
    console.log(`  - 自然サイズ: ${img.naturalWidth}x${img.naturalHeight}`);
    console.log(`  - 画像スタイル: display=${img.style.display}, visibility=${img.style.visibility}`);
    console.log(`  - 親要素スタイル: display=${parentContainer ? parentContainer.style.display : 'unknown'}`);
    
    // 🔥 重要：現在表示すべき状態かチェック
    const shouldBeVisible = (type === 'problem' && !showingAnswer) || (type === 'answer' && showingAnswer);
    
    if (shouldBeVisible && !isVisible) {
        console.warn(`⚠️ 表示すべき画像が非表示: ${imageId} (showingAnswer=${showingAnswer})`);
    } else if (!shouldBeVisible && isVisible) {
        console.warn(`⚠️ 非表示にすべき画像が表示: ${imageId} (showingAnswer=${showingAnswer})`);
    } else {
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

// ========== デバッグ機能（検証強化版） ==========
function debugStatus() {
    console.log("=== デバッグ情報（検証強化版） ===");
    console.log("カード数:", cards.length);
    console.log("現在のインデックス:", currentIndex);
    console.log("解答表示中:", showingAnswer);
    console.log("プリレンダリングカード数:", prerenderedCards.length);
    console.log("画像読み込み状況:", imageLoadTracker);
    
    // 各画像の詳細状況と表示すべき状態
    console.log("=== 画像詳細状況 ===");
    Object.keys(imageLoadTracker.imageStatus).forEach(function(imageId) {
        const status = imageLoadTracker.imageStatus[imageId];
        const shouldBeVisible = (status.type === 'problem' && !showingAnswer) || (status.type === 'answer' && showingAnswer);
        console.log(`${imageId}:`, {...status, shouldBeVisible: shouldBeVisible});
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
            problem_opacity: problemDiv ? problemDiv.style.opacity : "not found",
            should_be_visible: !showingAnswer
        });
        
        console.log("解答部分:", {
            answer_display: answerDiv ? answerDiv.style.display : "not found",
            answer_visibility: answerDiv ? answerDiv.style.visibility : "not found", 
            answer_opacity: answerDiv ? answerDiv.style.opacity : "not found",
            should_be_visible: showingAnswer
        });
        
        // 画像要素の詳細確認
        const problemImg = problemDiv ? problemDiv.querySelector('img') : null;
        const answerImg = answerDiv ? answerDiv.querySelector('img') : null;
        
        if (problemImg) {
            const problemVisible = problemImg.offsetParent !== null && problemImg.offsetWidth > 0;
            console.log("問題画像詳細:", {
                id: problemImg.id,
                src: problemImg.src,
                complete: problemImg.complete,
                naturalWidth: problemImg.naturalWidth,
                naturalHeight: problemImg.naturalHeight,
                offsetWidth: problemImg.offsetWidth,
                offsetHeight: problemImg.offsetHeight,
                actually_visible: problemVisible,
                should_be_visible: !showingAnswer,
                display: problemImg.style.display,
                visibility: problemImg.style.visibility,
                opacity: problemImg.style.opacity,
                status_ok: problemVisible === !showingAnswer
            });
        } else {
            console.log("問題画像: なし");
        }
        
        if (answerImg) {
            const answerVisible = answerImg.offsetParent !== null && answerImg.offsetWidth > 0;
            console.log("解答画像詳細:", {
                id: answerImg.id,
                src: answerImg.src,
                complete: answerImg.complete,
                naturalWidth: answerImg.naturalWidth,
                naturalHeight: answerImg.naturalHeight,
                offsetWidth: answerImg.offsetWidth,
                offsetHeight: answerImg.offsetHeight,
                actually_visible: answerVisible,
                should_be_visible: showingAnswer,
                display: answerImg.style.display,
                visibility: answerImg.style.visibility,
                opacity: answerImg.style.opacity,
                status_ok: answerVisible === showingAnswer
            });
        } else {
            console.log("解答画像: なし");
        }
    }
}

// ========== 画像修復関数 ==========
function fixAllImages() {
    console.log("🛠️ 全画像修復を実行（表示制御修正版）");
    
    const currentCard = prerenderedCards[currentIndex];
    if (!currentCard) return;
    
    const problemDiv = currentCard.querySelector('.problem-container');
    const answerDiv = currentCard.querySelector('.answer-container');
    
    if (showingAnswer) {
        // 解答表示中：問題を非表示、解答を表示
        if (problemDiv) {
            problemDiv.style.display = 'none';
            problemDiv.style.visibility = 'hidden';
            problemDiv.style.opacity = '0';
            
            const problemImg = problemDiv.querySelector('img');
            if (problemImg) {
                problemImg.style.display = 'none';
                problemImg.style.visibility = 'hidden';
                problemImg.style.opacity = '0';
            }
        }
        
        if (answerDiv) {
            answerDiv.style.display = 'flex';
            answerDiv.style.visibility = 'visible';
            answerDiv.style.opacity = '1';
            
            const answerImg = answerDiv.querySelector('img');
            if (answerImg) {
                answerImg.style.display = 'block';
                answerImg.style.visibility = 'visible';
                answerImg.style.opacity = '1';
            }
        }
        
        console.log("🔧 解答表示状態に修復完了");
    } else {
        // 問題表示中：解答を非表示、問題を表示
        if (answerDiv) {
            answerDiv.style.display = 'none';
            answerDiv.style.visibility = 'hidden';
            answerDiv.style.opacity = '0';
            
            const answerImg = answerDiv.querySelector('img');
            if (answerImg) {
                answerImg.style.display = 'none';
                answerImg.style.visibility = 'hidden';
                answerImg.style.opacity = '0';
            }
        }
        
        if (problemDiv) {
            problemDiv.style.display = 'flex';
            problemDiv.style.visibility = 'visible';
            problemDiv.style.opacity = '1';
            
            const problemImg = problemDiv.querySelector('img');
            if (problemImg) {
                problemImg.style.display = 'block';
                problemImg.style.visibility = 'visible';
                problemImg.style.opacity = '1';
            }
        }
        
        console.log("🔧 問題表示状態に修復完了");
    }
    
    // 修復後の状態確認
    setTimeout(debugStatus, 500);
}

// ========== 初期化（表示制御強化版） ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔧 表示制御修正版初期化開始");
    
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません");
        return;
    }
    
    cards = shuffle(rawCards.slice());
    currentIndex = 0;
    showingAnswer = false; // 🔥 重要：必ず問題表示から開始
    isPracticeMode = typeof mode !== 'undefined' && (mode === 'practice' || mode === 'chunk_practice');
    
    console.log("📊 カードデータ: " + cards.length + "枚");
    console.log("📚 練習モード: " + isPracticeMode);
    console.log("🎯 初期表示状態: 問題表示 (showingAnswer=" + showingAnswer + ")");
    
    prerenderAllCards();
    setupInstantEvents();
    setupInstantKeyboard();
    
    // 初期表示状態を段階的に設定
    setTimeout(function() {
        console.log("🎯 初期表示状態設定開始");
        forceShowFirstCard();
    }, 500);
    
    // デバッグ情報を表示
    setTimeout(function() {
        console.log("📊 初期化完了後のデバッグ情報:");
        debugStatus();
    }, 1500);
    
    console.log("🔧 表示制御修正版初期化完了");
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

console.log("🔧 表示制御修正版読み込み完了");